"""M1.6 kıyas ekranı testleri.

Kıyas mantığı: pencere = son resmi TÜFE dönemi vs 12 ay öncesi (yıllık),
sepet = harcama içeren son ay (weights_period). Sayfa veri eksikken 500
vermek yerine Türkçe ipucu gösterir.
"""

import os
from datetime import date
from decimal import Decimal

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from enflasyonum import crud
from enflasyonum.main import app
from enflasyonum.personal_index import compute_personal_index


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


@pytest.fixture()
def client(db_url):
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Motor: weights_period — sepet ayı fiyat penceresinden ayrı
# ---------------------------------------------------------------------------


def test_weights_period_separates_basket_from_window(session):
    """Harcama SADECE temmuzda; pencere haziran->temmuz.

    weights_period verilmezse baz ayda (haziran) harcama yok -> hata.
    weights_period=temmuz ile sepet temmuzdan gelir, göreli 126/120=1.05
    -> endeks 105.
    """
    crud.add_expense(
        session,
        category_name="gıda",
        description="market",
        amount=Decimal("750.00"),
        spent_at=date(2026, 7, 10),
    )
    crud.upsert_official_cpi(session, period=date(2026, 6, 1), index_value=Decimal("120"))
    crud.upsert_official_cpi(session, period=date(2026, 7, 1), index_value=Decimal("126"))

    r = compute_personal_index(
        session,
        base=date(2026, 6, 1),
        current=date(2026, 7, 1),
        weights_period=date(2026, 7, 1),
    )
    assert r.index_value == Decimal("105.000000")
    assert r.weights == {"gıda": Decimal("750.00")}


# ---------------------------------------------------------------------------
# Ekran: mutlu yol
# ---------------------------------------------------------------------------


def test_comparison_shows_two_numbers(session, client):
    """Yıllık pencere 2025-08 -> 2026-08: 100 -> 138.5 = %38.50.

    M1'de kişisel endeks manşete düştüğü için iki sayı da %38.50 olmalı;
    ekran her ikisini de göstermeli.
    """
    crud.upsert_official_cpi(session, period=date(2025, 8, 1), index_value=Decimal("100"))
    crud.upsert_official_cpi(
        session, period=date(2026, 8, 1), index_value=Decimal("138.5")
    )
    crud.add_expense(
        session,
        category_name="gıda",
        description="market",
        amount=Decimal("600.00"),
        spent_at=date(2026, 8, 15),
    )
    crud.add_expense(
        session,
        category_name="ulaşım",
        description="akbil",
        amount=Decimal("400.00"),
        spent_at=date(2026, 8, 16),
    )

    page = client.get("/").text
    assert "Senin enflasyonun" in page
    assert "Resmi TÜFE" in page
    assert page.count("38.50") >= 2
    assert "2025-08" in page and "2026-08" in page


def test_comparison_weight_breakdown_visible(session, client):
    """'Bu sayı nereden geldi?' dökümü: kategori payları görünür."""
    crud.upsert_official_cpi(session, period=date(2025, 8, 1), index_value=Decimal("100"))
    crud.upsert_official_cpi(session, period=date(2026, 8, 1), index_value=Decimal("110"))
    crud.add_expense(
        session,
        category_name="gıda",
        description="market",
        amount=Decimal("600.00"),
        spent_at=date(2026, 8, 15),
    )
    crud.add_expense(
        session,
        category_name="ulaşım",
        description="akbil",
        amount=Decimal("400.00"),
        spent_at=date(2026, 8, 16),
    )

    page = client.get("/").text
    assert "Bu sayı nereden geldi?" in page
    assert "%60.00" in page  # gıda payı 600/1000
    assert "%40.00" in page  # ulaşım payı 400/1000


# ---------------------------------------------------------------------------
# Ekran: veri eksikken ipuçları (asla 500 yok)
# ---------------------------------------------------------------------------


def test_hint_when_no_cpi(session, client):
    crud.add_expense(
        session,
        category_name="gıda",
        description="market",
        amount=Decimal("100.00"),
        spent_at=date(2026, 8, 15),
    )
    r = client.get("/")
    assert r.status_code == 200
    assert "Resmi TÜFE verisi yok" in r.text


def test_hint_when_no_expenses(session, client):
    crud.upsert_official_cpi(session, period=date(2026, 8, 1), index_value=Decimal("138.5"))
    r = client.get("/")
    assert r.status_code == 200
    assert "en az bir harcama gir" in r.text


def test_hint_when_base_period_missing(session, client):
    """Sadece güncel dönem var, 12 ay öncesi yok -> hesap ipucuyla düşer."""
    crud.upsert_official_cpi(session, period=date(2026, 8, 1), index_value=Decimal("138.5"))
    crud.add_expense(
        session,
        category_name="gıda",
        description="market",
        amount=Decimal("100.00"),
        spent_at=date(2026, 8, 15),
    )
    r = client.get("/")
    assert r.status_code == 200
    assert "Kıyas hesaplanamadı" in r.text
    assert "2025-08" in r.text
