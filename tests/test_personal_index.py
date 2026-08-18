import os
from datetime import date
from decimal import Decimal

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from enflasyonum import crud
from enflasyonum.personal_index import (
    PersonalIndexError,
    category_weights,
    compute_personal_index,
    headline_relative,
    laspeyres,
)


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


# ---------------------------------------------------------------------------
# Saf çekirdek: laspeyres() — DB'siz, elle doğrulanmış örnekler
# ---------------------------------------------------------------------------


def test_laspeyres_hand_verified_example():
    """Elle doğrulama (M1.5 kabul kriteri):

    Baz ay harcaması: gıda 600 TL, ulaşım 400 TL (toplam 1000 TL).
    Göreliler: gıda %10 zam (1.10), ulaşım %5 zam (1.05).

        L = 100 * (600*1.10 + 400*1.05) / 1000
          = 100 * (660 + 420) / 1000
          = 100 * 1080 / 1000
          = 108.0  ->  kişisel enflasyon %8.0
    """
    weights = {"gıda": Decimal("600"), "ulaşım": Decimal("400")}
    relatives = {"gıda": Decimal("1.10"), "ulaşım": Decimal("1.05")}
    assert laspeyres(weights, relatives) == Decimal("108.000000")


def test_laspeyres_single_category_equals_relative():
    # Tek kategori: endeks = 100 * göreli (ağırlık sadeleşir).
    out = laspeyres({"gıda": Decimal("250")}, {"gıda": Decimal("1.315000")})
    assert out == Decimal("131.500000")


def test_laspeyres_six_decimal_quantize():
    # 1/3 gibi sonsuz ondalık üretimi 6 haneye yuvarlanmalı.
    weights = {"a": Decimal("1"), "b": Decimal("2")}
    relatives = {"a": Decimal("1"), "b": Decimal("2")}
    # 100 * (1*1 + 2*2) / 3 = 500/3 = 166.666666...
    assert laspeyres(weights, relatives) == Decimal("166.666667")


def test_laspeyres_empty_weights_raises():
    with pytest.raises(PersonalIndexError, match="agirlik yok"):
        laspeyres({}, {})


def test_laspeyres_zero_total_raises():
    with pytest.raises(PersonalIndexError, match="sifir"):
        laspeyres({"gıda": Decimal("0")}, {"gıda": Decimal("1.1")})


def test_laspeyres_negative_weight_raises():
    with pytest.raises(PersonalIndexError, match="negatif"):
        laspeyres({"gıda": Decimal("-5")}, {"gıda": Decimal("1.1")})


def test_laspeyres_missing_relative_raises():
    with pytest.raises(PersonalIndexError, match="gorelisi eksik"):
        laspeyres({"gıda": Decimal("100")}, {})


# ---------------------------------------------------------------------------
# DB katmanı: ağırlıklar, manşet göreli, uçtan uca hesap
# ---------------------------------------------------------------------------


def _seed_expenses(session):
    crud.add_expense(
        session,
        category_name="gıda",
        description="market",
        amount=Decimal("600.00"),
        spent_at=date(2026, 6, 5),
    )
    crud.add_expense(
        session,
        category_name="ulaşım",
        description="akbil",
        amount=Decimal("400.00"),
        spent_at=date(2026, 6, 20),
    )


def test_category_weights_groups_by_month(session):
    _seed_expenses(session)
    # Baz ay dışına düşen harcama ağırlığa girmemeli.
    crud.add_expense(
        session,
        category_name="gıda",
        description="temmuz marketi",
        amount=Decimal("999.00"),
        spent_at=date(2026, 7, 1),
    )
    w = category_weights(session, date(2026, 6, 1))
    assert w == {"gıda": Decimal("600.00"), "ulaşım": Decimal("400.00")}


def test_headline_relative_from_official_cpi(session):
    crud.upsert_official_cpi(session, period=date(2026, 6, 1), index_value=Decimal("120"))
    crud.upsert_official_cpi(session, period=date(2026, 7, 1), index_value=Decimal("126"))
    assert headline_relative(session, date(2026, 6, 1), date(2026, 7, 1)) == Decimal("1.05")


def test_headline_relative_missing_period_raises(session):
    crud.upsert_official_cpi(session, period=date(2026, 6, 1), index_value=Decimal("120"))
    with pytest.raises(PersonalIndexError, match="2026-07"):
        headline_relative(session, date(2026, 6, 1), date(2026, 7, 1))


def test_compute_personal_index_end_to_end(session):
    """M1 davranışı: tüm kategoriler manşet göreliye düşer.

    Manşet: 120 -> 126 (göreli 1.05). Ağırlık dağılımından bağımsız olarak
    endeks 105 olmalı (tek göreli varken Laspeyres sadeleşir) —
    elle: 100*(600*1.05 + 400*1.05)/1000 = 105.
    """
    _seed_expenses(session)
    crud.upsert_official_cpi(session, period=date(2026, 6, 1), index_value=Decimal("120"))
    crud.upsert_official_cpi(session, period=date(2026, 7, 1), index_value=Decimal("126"))

    r = compute_personal_index(session, base=date(2026, 6, 1), current=date(2026, 7, 1))
    assert r.index_value == Decimal("105.000000")
    assert r.inflation_pct == Decimal("5.000000")
    assert r.weights == {"gıda": Decimal("600.00"), "ulaşım": Decimal("400.00")}


def test_compute_personal_index_category_relatives_override(session):
    """M2 hazırlığı: kategoriye özel göreli manşeti ezer.

    gıda 1.10 (verildi), ulaşım manşete düşer (1.05):
    100*(600*1.10 + 400*1.05)/1000 = 108.
    """
    _seed_expenses(session)
    crud.upsert_official_cpi(session, period=date(2026, 6, 1), index_value=Decimal("120"))
    crud.upsert_official_cpi(session, period=date(2026, 7, 1), index_value=Decimal("126"))

    r = compute_personal_index(
        session,
        base=date(2026, 6, 1),
        current=date(2026, 7, 1),
        category_relatives={"gıda": Decimal("1.10")},
    )
    assert r.index_value == Decimal("108.000000")


def test_compute_personal_index_no_expenses_raises(session):
    crud.upsert_official_cpi(session, period=date(2026, 6, 1), index_value=Decimal("120"))
    crud.upsert_official_cpi(session, period=date(2026, 7, 1), index_value=Decimal("126"))
    with pytest.raises(PersonalIndexError, match="hic harcama yok"):
        compute_personal_index(session, base=date(2026, 6, 1), current=date(2026, 7, 1))
