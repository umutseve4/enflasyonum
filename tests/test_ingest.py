import json
import os
from datetime import date
from decimal import Decimal

import httpx
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from enflasyonum import crud, ingest


@pytest.fixture()
def session(tmp_path, monkeypatch):
    url = os.environ.get("DATABASE_URL") or f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")
    engine = create_engine(url)
    factory = sessionmaker(bind=engine)
    with factory() as s:
        yield s
    engine.dispose()
    command.downgrade(cfg, "base")


def test_months_back():
    assert ingest.months_back(date(2026, 8, 18), 24) == date(2024, 8, 1)
    assert ingest.months_back(date(2026, 1, 5), 2) == date(2025, 11, 1)


def test_series_is_2025_base():
    # TÜİK Ocak 2026'da 2003=100 bazını bıraktı; eski koda dönüş regresyondur.
    assert ingest.SERIES == "TP.TUKFIY2025.GENEL"
    assert ingest.SERIES_JSON_KEY == "TP_TUKFIY2025_GENEL"


def test_parse_period_both_orders():
    assert ingest.parse_period("2024-1") == date(2024, 1, 1)
    assert ingest.parse_period("12-2025") == date(2025, 12, 1)


def test_parse_items_skips_null_and_garbage():
    items = [
        {"Tarih": "2025-6", "TP_TUKFIY2025_GENEL": "98.395995"},
        {"Tarih": "2025-7", "TP_TUKFIY2025_GENEL": None},
        {"Tarih": "bozuk", "TP_TUKFIY2025_GENEL": "1"},
        {"Tarih": "2025-8", "TP_TUKFIY2025_GENEL": "abc"},
    ]
    parsed = ingest.parse_items(items)
    assert parsed == [(date(2025, 6, 1), Decimal("98.395995"))]


def test_ingest_idempotent(session):
    parsed = [
        (date(2025, 6, 1), Decimal("98.395995")),
        (date(2025, 7, 1), Decimal("100.421925")),
    ]
    assert ingest.ingest_cpi(session, parsed) == 2
    assert ingest.ingest_cpi(session, parsed) == 2  # ikinci kosu
    rows = crud.list_official_cpi(session)
    assert len(rows) == 2  # ciftlenme yok
    assert rows[0].index_value == Decimal("98.395995")


def test_fetch_sends_key_header_and_parses(monkeypatch):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["key"] = request.headers.get("key")
        body = {
            "totalCount": 1,
            "items": [{"Tarih": "2025-6", "TP_TUKFIY2025_GENEL": "98.395995"}],
        }
        return httpx.Response(200, content=json.dumps(body))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    items = ingest.fetch_cpi_items(
        "test-key", date(2024, 8, 1), date(2026, 8, 18), client=client
    )
    assert captured["key"] == "test-key"
    assert "series=TP.TUKFIY2025.GENEL" in captured["url"]
    assert "startDate=01-08-2024" in captured["url"]
    assert "endDate=18-08-2026" in captured["url"]
    assert items == [{"Tarih": "2025-6", "TP_TUKFIY2025_GENEL": "98.395995"}]


def test_fetch_raises_on_403():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(httpx.HTTPStatusError):
        ingest.fetch_cpi_items("bad", date(2024, 8, 1), date(2026, 8, 18), client=client)


def test_fetch_custom_series_in_url():
    """M2.1: series_code parametresi URL'e yansımalı."""
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, content=json.dumps({"items": []}))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    ingest.fetch_cpi_items(
        "test-key",
        date(2024, 8, 1),
        date(2026, 8, 18),
        series_code="TP.TUKFIY2025.13",
        client=client,
    )
    assert "series=TP.TUKFIY2025.13" in captured["url"]


def test_parse_items_custom_value_key():
    """M2.1: alt seri JSON anahtarıyla ayrıştırma."""
    items = [{"Tarih": "2025-6", "TP_TUKFIY2025_13": "97.5"}]
    parsed = ingest.parse_items(items, value_key="TP_TUKFIY2025_13")
    assert parsed == [(date(2025, 6, 1), Decimal("97.5"))]


def test_ingest_same_period_two_series_no_conflict(session):
    """M2.1: aynı dönem iki seriye yazılır, birbirini ezmez."""
    parsed_headline = [(date(2025, 6, 1), Decimal("100"))]
    parsed_sub = [(date(2025, 6, 1), Decimal("90"))]
    assert ingest.ingest_cpi(session, parsed_headline) == 1
    assert ingest.ingest_cpi(session, parsed_sub, series_code="TP.TUKFIY2025.13") == 1

    headline_rows = crud.list_official_cpi(session)
    assert len(headline_rows) == 1
    assert headline_rows[0].index_value == Decimal("100")

    sub_rows = crud.list_official_cpi(session, series_code="TP.TUKFIY2025.13")
    assert len(sub_rows) == 1
    assert sub_rows[0].index_value == Decimal("90")
