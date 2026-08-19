"""M2.2 paylaşılabilir özet kartı (/card.svg) testleri.

Kart ana sayfayla aynı kıyas verisini SVG olarak sunar. İlke aynı:
veri eksikken 500 yerine Türkçe ipucu kartı döner. Kullanıcı girdisi
(kategori adı) XML'e karşı escape edilir — SVG injection kapısı yok.
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
from enflasyonum.card import render_card_svg
from enflasyonum.main import app


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
# Birim: render_card_svg saf fonksiyon
# ---------------------------------------------------------------------------


def _sample_comparison() -> dict:
    return {
        "personal_pct": Decimal("47.50"),
        "official_pct": Decimal("31.75"),
        "diff_pct": Decimal("15.75"),
        "base_period": date(2025, 8, 1),
        "current_period": date(2026, 8, 1),
        "basket_period": date(2026, 8, 1),
        "weight_rows": [
            {
                "category": "kozmetik",
                "amount": Decimal("550.00"),
                "share_pct": Decimal("91.67"),
                "relative_pct": Decimal("50.00"),
                "own_series": True,
            },
            {
                "category": "zımbırtı",
                "amount": Decimal("50.00"),
                "share_pct": Decimal("8.33"),
                "relative_pct": Decimal("31.75"),
                "own_series": False,
            },
        ],
        "weights_total": Decimal("600.00"),
    }


def test_render_card_contains_both_numbers_and_is_valid_xml():
    svg = render_card_svg(_sample_comparison(), None, "0.3.0")
    minidom.parseString(svg)  # geçersiz XML burada patlar
    assert "%47.50" in svg
    assert "%31.75" in svg
    assert "+15.75 puan" in svg
    assert "2025-08 → 2026-08" in svg
    assert "%31.75*" in svg  # manşete düşen kategori yıldızlı
    assert "enflasyonum v0.3.0" in svg


def test_render_card_negative_diff_signed():
    comp = _sample_comparison()
    comp["diff_pct"] = Decimal("-3.10")
    assert "-3.10 puan" in render_card_svg(comp, None, "0.3.0")


def test_render_card_escapes_user_category():
    """Kategori adı XML bozamaz ve script enjekte edemez."""
    comp = _sample_comparison()
    comp["weight_rows"][0]["category"] = 'koz<metik>&"'
    svg = render_card_svg(comp, None, "0.3.0")
    minidom.parseString(svg)
    assert "<metik>" not in svg
    assert "&lt;metik&gt;&amp;" in svg


def test_render_card_hint_when_no_data():
    svg = render_card_svg(None, "Kıyas için önce en az bir harcama gir.", "0.3.0")
    minidom.parseString(svg)
    assert "en az bir harcama gir" in svg


# ---------------------------------------------------------------------------
# Endpoint: /card.svg
# ---------------------------------------------------------------------------


def test_card_endpoint_hint_when_empty_db(client):
    r = client.get("/card.svg")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/svg+xml")
    assert "Resmi TÜFE verisi yok" in r.text


def test_card_endpoint_renders_comparison(session, client):
    """Ana sayfadaki senaryonun aynısı: 100 -> 138.5 = %38.50 iki tarafta."""
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

    r = client.get("/card.svg")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/svg+xml")
    minidom.parseString(r.text)
    assert r.text.count("38.50") >= 2
    assert "2025-08 → 2026-08" in r.text
    assert r.headers["cache-control"] == "no-store"


def test_index_links_to_card(session, client):
    """Ana sayfada paylaşım linki, kıyas verisi varken görünür."""
    crud.upsert_official_cpi(session, period=date(2025, 8, 1), index_value=Decimal("100"))
    crud.upsert_official_cpi(session, period=date(2026, 8, 1), index_value=Decimal("110"))
    crud.add_expense(
        session,
        category_name="gıda",
        description="market",
        amount=Decimal("100.00"),
        spent_at=date(2026, 8, 15),
    )
    page = client.get("/").text
    assert 'href="/card.svg"' in page
