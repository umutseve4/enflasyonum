import os

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from enflasyonum.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    url = os.environ.get("DATABASE_URL") or f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")
    with TestClient(app) as c:
        yield c
    command.downgrade(cfg, "base")


def test_index_renders_form(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Enflasyonumdan ne haber?" in r.text
    assert '<form method="post" action="/expenses"' in r.text


def test_post_expense_then_listed(client):
    r = client.post(
        "/expenses",
        data={
            "description": "süt",
            "amount": "42.50",
            "category": "gıda",
            "spent_at": "2026-08-18",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/"

    page = client.get("/")
    assert "süt" in page.text
    assert "gıda" in page.text
    assert "42.50" in page.text


def test_post_expense_comma_decimal(client):
    r = client.post(
        "/expenses",
        data={
            "description": "ekmek",
            "amount": "15,75",
            "category": "gıda",
            "spent_at": "2026-08-18",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert "15.75" in client.get("/").text


def test_post_invalid_amount_rejected(client):
    r = client.post(
        "/expenses",
        data={
            "description": "hata",
            "amount": "abc",
            "category": "test",
            "spent_at": "2026-08-18",
        },
    )
    assert r.status_code == 422
    assert "hata" not in client.get("/").text.replace("Tutar sayı değil", "")


def test_post_negative_amount_rejected(client):
    r = client.post(
        "/expenses",
        data={
            "description": "eksi",
            "amount": "-5",
            "category": "test",
            "spent_at": "2026-08-18",
        },
    )
    assert r.status_code == 422
