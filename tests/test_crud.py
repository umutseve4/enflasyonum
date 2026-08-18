import os
from datetime import date
from decimal import Decimal

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from enflasyonum import crud


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
    with factory() as s:
        yield s
    engine.dispose()


def test_migration_creates_tables(db_url):
    engine = create_engine(db_url)
    tables = set(inspect(engine).get_table_names())
    engine.dispose()
    assert {"categories", "expenses", "official_cpi"} <= tables


def test_expense_crud_roundtrip(session):
    exp = crud.add_expense(
        session,
        category_name="gıda",
        description="süt",
        amount=Decimal("42.50"),
        spent_at=date(2026, 8, 18),
    )
    assert exp.id is not None

    rows = crud.list_expenses(session)
    assert len(rows) == 1
    assert rows[0].description == "süt"
    assert rows[0].amount == Decimal("42.50")

    assert crud.monthly_total(session, 2026, 8) == Decimal("42.50")
    assert crud.monthly_total(session, 2026, 7) == Decimal("0")


def test_list_expenses_date_filter(session):
    crud.add_expense(
        session,
        category_name="gıda",
        description="ekmek",
        amount=Decimal("15.00"),
        spent_at=date(2026, 8, 1),
    )
    crud.add_expense(
        session,
        category_name="ulaşım",
        description="otobüs",
        amount=Decimal("20.00"),
        spent_at=date(2026, 8, 10),
    )
    rows = crud.list_expenses(session, start=date(2026, 8, 5))
    assert [r.description for r in rows] == ["otobüs"]


def test_category_get_or_create_reuses(session):
    a = crud.get_or_create_category(session, "gıda")
    b = crud.get_or_create_category(session, "gıda")
    assert a.id == b.id


def test_official_cpi_upsert_idempotent(session):
    p = date(2026, 7, 1)
    crud.upsert_official_cpi(session, period=p, index_value=Decimal("2543.1"))
    crud.upsert_official_cpi(session, period=p, index_value=Decimal("2550.0"))

    rows = crud.list_official_cpi(session)
    assert len(rows) == 1
    assert rows[0].index_value == Decimal("2550.0")


def test_official_cpi_same_period_different_series(session):
    """M2.1: aynı dönem, farklı seri -> iki ayrı satır, çakışma yok."""
    p = date(2026, 7, 1)
    crud.upsert_official_cpi(session, period=p, index_value=Decimal("100"))
    crud.upsert_official_cpi(
        session, period=p, index_value=Decimal("90"), series_code="TP.TUKFIY2025.13"
    )

    headline_rows = crud.list_official_cpi(session)
    assert len(headline_rows) == 1
    assert headline_rows[0].index_value == Decimal("100")

    sub_rows = crud.list_official_cpi(session, series_code="TP.TUKFIY2025.13")
    assert len(sub_rows) == 1
    assert sub_rows[0].index_value == Decimal("90")
