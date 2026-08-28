from datetime import date, timedelta
from decimal import Decimal

from enflasyonum.models import Category, Expense


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


def test_usage_progress_counts_distinct_days_only(client, db_session):
    _add_expense(db_session, date(2026, 8, 1))
    _add_expense(db_session, date(2026, 8, 1))
    _add_expense(db_session, date(2026, 8, 2))

    payload = client.get("/usage-progress").json()
    assert payload == {
        "distinct_days": 2,
        "target_days": 14,
        "remaining_days": 12,
        "complete": False,
    }
    serialized = str(payload)
    assert "private detail" not in serialized
    assert "amount" not in payload
    assert "category" not in payload
    assert "dates" not in payload


def test_usage_progress_completes_at_fourteen_days(client, db_session):
    start = date(2026, 8, 1)
    for offset in range(14):
        _add_expense(db_session, start + timedelta(days=offset))

    assert client.get("/usage-progress").json() == {
        "distinct_days": 14,
        "target_days": 14,
        "remaining_days": 0,
        "complete": True,
    }


def test_usage_progress_remaining_never_negative(client, db_session):
    start = date(2026, 8, 1)
    for offset in range(15):
        _add_expense(db_session, start + timedelta(days=offset))

    payload = client.get("/usage-progress").json()
    assert payload["distinct_days"] == 15
    assert payload["remaining_days"] == 0
    assert payload["complete"] is True
