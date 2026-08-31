import base64
import os
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

import enflasyonum.main as main_module
from enflasyonum import __version__, crud
from enflasyonum.main import PUBLIC_ALLOWLIST, app
from enflasyonum.models import Expense


@pytest.fixture()
def db_url(tmp_path, monkeypatch):
    url = os.environ.get("DATABASE_URL") or f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")
    yield url
    command.downgrade(cfg, "base")


@pytest.fixture()
def session(db_url):
    engine = create_engine(db_url)
    factory = sessionmaker(bind=engine)
    with factory() as db_session:
        yield db_session
    engine.dispose()


@pytest.fixture()
def client(db_url):
    with TestClient(app) as test_client:
        yield test_client


def _auth_header(username: str, token: str) -> dict[str, str]:
    raw = f"{username}:{token}".encode("utf-8")
    return {"Authorization": f"Basic {base64.b64encode(raw).decode('ascii')}"}


def _assert_private_cache_headers(response):
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"
    assert "authorization" in response.headers["vary"].lower()


def test_missing_owner_token_fails_closed_with_503(client, monkeypatch):
    canary = "private-canary-should-not-leak"
    counters = {"factory": 0, "index": 0}

    def _factory():
        counters["factory"] += 1
        raise AssertionError("DB factory should not be called")

    def _index_context(*args, **kwargs):
        counters["index"] += 1
        return {"canary": canary}

    monkeypatch.setattr("enflasyonum.main.create_session_factory", _factory)
    monkeypatch.setattr("enflasyonum.main._index_context", _index_context)
    monkeypatch.setenv("ENFLASYONUM_OWNER_TOKEN", "   ")
    response = client.get("/")
    assert response.status_code == 503
    assert response.json() == {"detail": "Service unavailable"}
    assert canary not in response.text
    assert counters == {"factory": 0, "index": 0}
    _assert_private_cache_headers(response)


def test_missing_credentials_returns_401(client):
    response = client.get("/")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Basic"
    _assert_private_cache_headers(response)


def test_invalid_credentials_returns_401(client):
    response = client.get("/", headers=_auth_header("owner", "wrong-token"))
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Basic"
    _assert_private_cache_headers(response)


@pytest.mark.parametrize(
    "authorization",
    [
        "Basic !!!",
        "Basic /w==",
        "Basic b3duZXI=",
        "Basic",
        "Bearer dGVzdA==",
    ],
)
def test_malformed_authorization_returns_401(client, authorization):
    response = client.get("/", headers={"Authorization": authorization})
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Basic"
    _assert_private_cache_headers(response)


def test_both_credential_comparisons_execute_when_username_is_wrong(client, monkeypatch):
    calls = []
    real_compare_digest = __import__("hmac").compare_digest

    def compare_digest(left, right):
        calls.append((left, right))
        return real_compare_digest(left, right)

    monkeypatch.setattr(
        main_module, "hmac", SimpleNamespace(compare_digest=compare_digest)
    )
    token = os.environ["ENFLASYONUM_OWNER_TOKEN"]
    response = client.get("/", headers=_auth_header("wrong-owner", token))

    assert response.status_code == 401
    assert calls == [("wrong-owner", "owner"), (token, token)]


@pytest.mark.parametrize(
    ("configured_username", "request_username"),
    [("   ", "owner"), ("  custom-owner  ", "custom-owner")],
)
def test_owner_username_is_trimmed_and_blank_falls_back_to_owner(
    client, monkeypatch, configured_username, request_username
):
    monkeypatch.setenv("ENFLASYONUM_OWNER_USERNAME", configured_username)
    token = os.environ["ENFLASYONUM_OWNER_TOKEN"]
    response = client.get("/", headers=_auth_header(request_username, token))

    assert response.status_code == 200
    _assert_private_cache_headers(response)


def test_valid_credentials_preserve_private_get_and_post_behavior(client, owner_auth_headers):
    page = client.get("/", headers=owner_auth_headers)
    assert page.status_code == 200
    assert "Enflasyonumdan ne haber?" in page.text
    _assert_private_cache_headers(page)

    post_response = client.post(
        "/expenses",
        data={
            "description": "market",
            "amount": "42.50",
            "category": "gıda",
            "spent_at": "2026-08-18",
        },
        headers=owner_auth_headers,
        follow_redirects=False,
    )
    assert post_response.status_code == 303
    assert post_response.headers["location"] == "/"
    _assert_private_cache_headers(post_response)

    follow = client.get("/", headers=owner_auth_headers)
    assert "market" in follow.text
    assert "42.50" in follow.text


def test_unauthorized_requests_do_not_invoke_private_db_or_render_helpers(client, monkeypatch):
    counters = {"factory": 0, "index": 0}

    def _factory():
        counters["factory"] += 1
        raise AssertionError("DB factory should not be called")

    def _index_context(*args, **kwargs):
        counters["index"] += 1
        raise AssertionError("Private helper should not be called")

    monkeypatch.setattr("enflasyonum.main.create_session_factory", _factory)
    monkeypatch.setattr("enflasyonum.main._index_context", _index_context)

    response = client.get("/")
    assert response.status_code == 401
    assert counters == {"factory": 0, "index": 0}


def test_authenticated_private_500_keeps_private_headers(
    db_url, owner_auth_headers, monkeypatch
):
    canary = "private-error-canary"

    def _boom(*args, **kwargs):
        raise RuntimeError(canary)

    monkeypatch.setattr("enflasyonum.main._index_context", _boom)

    with TestClient(app, raise_server_exceptions=False) as error_client:
        response = error_client.get("/", headers=owner_auth_headers)

    assert response.status_code == 500
    assert canary not in response.text
    _assert_private_cache_headers(response)


def test_public_health_and_usage_progress_remain_unauthenticated(client):
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok", "version": __version__}

    usage = client.get("/usage-progress")
    assert usage.status_code == 200
    assert usage.json() == {
        "distinct_days": 0,
        "target_days": 14,
        "remaining_days": 14,
        "complete": False,
    }


def test_query_strings_and_head_do_not_bypass_private_auth(client):
    assert client.get("/?q=1").status_code == 401
    assert client.head("/").status_code == 401
    assert client.head("/health").status_code == 200
    assert client.head("/usage-progress").status_code == 200


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/"),
        ("get", "/card.svg"),
        ("get", "/history.svg"),
        ("get", "/export.csv"),
        ("post", "/expenses"),
        ("get", "/docs"),
        ("get", "/redoc"),
        ("get", "/openapi.json"),
    ],
)
def test_named_private_routes_are_protected(client, method, path):
    kwargs = {}
    if method == "post":
        kwargs["data"] = {
            "description": "x",
            "amount": "1.00",
            "category": "test",
            "spent_at": "2026-08-18",
        }
        kwargs["follow_redirects"] = False
    response = getattr(client, method)(path, **kwargs)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Basic"
    _assert_private_cache_headers(response)


def test_public_allowlist_inventory_is_exact():
    assert PUBLIC_ALLOWLIST == {
        ("GET", "/health"),
        ("HEAD", "/health"),
        ("GET", "/usage-progress"),
        ("HEAD", "/usage-progress"),
    }


def test_private_default_applies_to_existing_get_routes(client):
    public = {"/health", "/usage-progress"}
    get_paths = {
        route.path
        for route in app.routes
        if getattr(route, "methods", None) and "GET" in route.methods
    }
    for path in get_paths:
        if path in public:
            continue
        response = client.get(path)
        assert response.status_code == 401
        _assert_private_cache_headers(response)


def test_denied_write_attempts_do_not_change_db_rows(client, session):
    crud.add_expense(
        session,
        category_name="gıda",
        description="seed",
        amount=Decimal("10.00"),
        spent_at=date(2026, 8, 1),
    )
    before_count = session.scalar(select(func.count(Expense.id)))
    before_rows = session.execute(
        select(Expense.spent_at, Expense.category_id, Expense.description, Expense.amount).order_by(
            Expense.id
        )
    ).all()

    unauthorized = client.post(
        "/expenses",
        data={
            "description": "denied",
            "amount": "99.99",
            "category": "x",
            "spent_at": "2026-08-18",
        },
        follow_redirects=False,
    )
    assert unauthorized.status_code == 401
    _assert_private_cache_headers(unauthorized)

    after_count = session.scalar(select(func.count(Expense.id)))
    after_rows = session.execute(
        select(Expense.spent_at, Expense.category_id, Expense.description, Expense.amount).order_by(
            Expense.id
        )
    ).all()
    assert after_count == before_count
    assert after_rows == before_rows
