import os
from datetime import date, timedelta
from decimal import Decimal

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from enflasyonum.main import app
from enflasyonum.models import Category, Expense


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


def _add_expense(session, spent_at: date) -> None:
    category = session.query(Category).filter_by(name="Test").first()
    if category is None:
        category = Category(name="Test")
        session.add(category)
        session.flush()
    session.add(
        Expense(
            amount=Decimal("10.00"),
            category_id=category.id,
            spent_at=spent_at,
            description="private detail",
        )
    )
    session.commit()


def test_usage_progress_empty(client):
    response = client.get("/usage-progress")
    assert response.status_code == 200
    assert response.json() == {
        "distinct_days": 0,
        "target_days": 14,
        "remaining_days": 14,
        "complete": False,
    }


def test_usage_progress_counts_distinct_days_only(client, session):
    _add_expense(session, date(2026, 8, 1))
    _add_expense(session, date(2026, 8, 1))
    _add_expense(session, date(2026, 8, 2))
    payload = client.get("/usage-progress").json()
    assert payload == {
        "distinct_days": 2,
        "target_days": 14,
        "remaining_days": 12,
        "complete": False,
    }
    assert "private detail" not in str(payload)
    assert set(payload) == {"distinct_days", "target_days", "remaining_days", "complete"}


def test_usage_progress_completes_at_fourteen_days(client, session):
    start = date(2026, 8, 1)
    for offset in range(14):
        _add_expense(session, start + timedelta(days=offset))
    assert client.get("/usage-progress").json() == {
        "distinct_days": 14,
        "target_days": 14,
        "remaining_days": 0,
        "complete": True,
    }


def test_usage_progress_remaining_never_negative(client, session):
    start = date(2026, 8, 1)
    for offset in range(15):
        _add_expense(session, start + timedelta(days=offset))
    payload = client.get("/usage-progress").json()
    assert payload["distinct_days"] == 15
    assert payload["remaining_days"] == 0
    assert payload["complete"] is True
