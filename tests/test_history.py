"""M2.3 harcama geçmişi grafiği (/history.svg) testleri.

Aynı ilke: veri yokken veya DB hatasında 500 yerine Türkçe ipucu döner;
SVG geçerli XML olmak zorunda. Aylık toplama saf Python fonksiyonu
olarak birim test edilir, endpoint gerçek DB üzerinden doğrulanır.
"""

import os
from datetime import date
from decimal import Decimal
from xml.dom import minidom

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from enflasyonum import crud
from enflasyonum.history import (
    HEIGHT,
    MAX_MONTHS,
    WIDTH,
    monthly_totals,
    render_history_svg,
)
from enflasyonum.main import app, get_session


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
# Birim: monthly_totals
# ---------------------------------------------------------------------------


def test_monthly_totals_aggregates_and_sorts():
    rows = [
        (date(2026, 8, 15), Decimal("10.00")),
        (date(2026, 7, 2), Decimal("5.00")),
        (date(2026, 8, 1), Decimal("2.50")),
    ]
    assert monthly_totals(rows) == [
        (date(2026, 7, 1), Decimal("5.00")),
        (date(2026, 8, 1), Decimal("12.50")),
    ]


def test_monthly_totals_keeps_last_12_months():
    rows = [
        (date(2024 + (m - 1) // 12, (m - 1) % 12 + 1, 1), Decimal("1"))
        for m in range(1, 15)  # 2024-01 .. 2025-02 = 14 ay
    ]
    totals = monthly_totals(rows)
    assert len(totals) == MAX_MONTHS
    assert totals[0][0] == date(2024, 3, 1)  # ilk 2 ay düştü


def test_monthly_totals_uses_calendar_window_not_active_months():
    """QA bulgusu (PR #12): pencere takvim ayı bazlıdır, aktif ay değil.

    2024-01 kaydı, son kayıt 2026-08 iken 12 aylık takvim penceresinin
    tamamen dışındadır — grafikte yan yana gösterilmemeli.
    """
    totals = monthly_totals(
        [(date(2024, 1, 5), Decimal("1")), (date(2026, 8, 2), Decimal("2"))]
    )
    assert totals == [(date(2026, 8, 1), Decimal("2"))]


def test_monthly_totals_fills_gaps_with_zero():
    """Pencere içindeki boş aylar 0 TL olarak görünür — eksen yanıltmaz."""
    totals = monthly_totals(
        [(date(2026, 5, 1), Decimal("10")), (date(2026, 8, 1), Decimal("20"))]
    )
    assert [p for p, _ in totals] == [
        date(2026, 5, 1),
        date(2026, 6, 1),
        date(2026, 7, 1),
        date(2026, 8, 1),
    ]
    assert totals[1][1] == Decimal("0")
    assert totals[2][1] == Decimal("0")


def test_monthly_totals_window_crosses_year_boundary():
    totals = monthly_totals(
        [(date(2025, 2, 3), Decimal("1")), (date(2026, 1, 9), Decimal("2"))]
    )
    assert len(totals) == MAX_MONTHS
    assert totals[0][0] == date(2025, 2, 1)
    assert totals[-1][0] == date(2026, 1, 1)


# ---------------------------------------------------------------------------
# Birim: render_history_svg saf fonksiyon
# ---------------------------------------------------------------------------


def test_render_history_bar_count_and_valid_xml():
    totals = [
        (date(2026, 6, 1), Decimal("100.00")),
        (date(2026, 7, 1), Decimal("250.00")),
        (date(2026, 8, 1), Decimal("50.00")),
    ]
    svg = render_history_svg(totals, "0.4.0")
    minidom.parseString(svg)  # geçersiz XML burada patlar
    assert svg.count('class="bar"') == 3
    assert "2026-07" in svg
    assert "250.00 TL" in svg
    assert "enflasyonum v0.4.0" in svg


def test_render_history_empty_shows_hint():
    svg = render_history_svg([], "0.4.0")
    minidom.parseString(svg)
    assert "Henüz harcama yok" in svg
    assert 'class="bar"' not in svg


def test_render_history_zero_total_does_not_crash():
    """Tutar pozitif doğrulanıyor ama savunmacı: max=0 bölme hatası yok."""
    svg = render_history_svg([(date(2026, 8, 1), Decimal("0"))], "0.4.0")
    minidom.parseString(svg)


def test_render_history_svg_contract_size_and_a11y():
    """Sözleşme: 800x360, viewBox ve erişilebilirlik nitelikleri sabit."""
    svg = render_history_svg([(date(2026, 8, 1), Decimal("10"))], "0.4.0")
    assert f'width="{WIDTH}"' in svg
    assert f'height="{HEIGHT}"' in svg
    assert f'viewBox="0 0 {WIDTH} {HEIGHT}"' in svg
    assert 'role="img"' in svg
    assert 'aria-label="Aylık harcama geçmişi grafiği"' in svg


# ---------------------------------------------------------------------------
# Endpoint: /history.svg
# ---------------------------------------------------------------------------


def test_history_endpoint_hint_when_empty_db(client):
    r = client.get("/history.svg")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/svg+xml")
    assert r.headers["cache-control"] == "no-store"
    assert "Henüz harcama yok" in r.text


def test_history_endpoint_renders_monthly_bars(session, client):
    crud.add_expense(
        session,
        category_name="gıda",
        description="market",
        amount=Decimal("100.00"),
        spent_at=date(2026, 7, 10),
    )
    crud.add_expense(
        session,
        category_name="gıda",
        description="market",
        amount=Decimal("40.00"),
        spent_at=date(2026, 8, 3),
    )
    crud.add_expense(
        session,
        category_name="ulaşım",
        description="bilet",
        amount=Decimal("10.00"),
        spent_at=date(2026, 8, 5),
    )
    r = client.get("/history.svg")
    assert r.status_code == 200
    minidom.parseString(r.text)
    assert r.text.count('class="bar"') == 2  # 2026-07 ve 2026-08
    assert "100.00 TL" in r.text
    assert "50.00 TL" in r.text  # 40 + 10 ay içinde toplandı


def test_history_endpoint_falls_back_on_db_error(client):
    """QA bulgusu (PR #12): DB hatasında 500 değil, 200 + hata kartı."""

    class BrokenSession:
        def execute(self, *args, **kwargs):
            raise RuntimeError("db down")

    app.dependency_overrides[get_session] = lambda: BrokenSession()
    try:
        r = client.get("/history.svg")
    finally:
        app.dependency_overrides.pop(get_session, None)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/svg+xml")
    assert r.headers["cache-control"] == "no-store"
    assert "oluşturulamadı" in r.text
    minidom.parseString(r.text)


def test_index_embeds_history_chart(client):
    page = client.get("/").text
    assert 'src="/history.svg"' in page


def test_index_links_history_in_new_tab(client):
    page = client.get("/").text
    assert '<a href="/history.svg" target="_blank"' in page
