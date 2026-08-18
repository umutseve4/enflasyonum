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


def test_parse_period_both_orders():
    assert ingest.parse_period("2024-1") == date(2024, 1, 1)
    assert ingest.parse_period("12-2025") == date(2025, 12, 1)


def test_parse_items_skips_null_and_garbage():
    items = [
        {"Tarih": "2025-6", "TP_FG_J0": "2915.27"},
        {"Tarih": "2025-7", "TP_FG_J0": None},
        {"Tarih": "bozuk", "TP_FG_J0": "1"},
        {"Tarih": "2025-8", "TP_FG_J0": "abc"},
    ]
    parsed = ingest.parse_items(items)
    assert parsed == [(date(2025, 6, 1), Decimal("2915.27"))]


def test_ingest_idempotent(session):
    parsed = [
        (date(2025, 6, 1), Decimal("2915.27")),
        (date(2025, 7, 1), Decimal("2980.44")),
    ]
    assert ingest.ingest_cpi(session, parsed) == 2
    assert ingest.ingest_cpi(session, parsed) == 2  # ikinci kosu
    rows = crud.list_official_cpi(session)
    assert len(rows) == 2  # ciftlenme yok
    assert rows[0].index_value == Decimal("2915.27")


def test_fetch_sends_key_header_and_parses(monkeypatch):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["key"] = request.headers.get("key")
        body = {
            "totalCount": 1,
            "items": [{"Tarih": "2025-6", "TP_FG_J0": "2915.27"}],
        }
        return httpx.Response(200, content=json.dumps(body))

    client = httpx.Client(transport=httpx.MockTransport(handler))
    items = ingest.fetch_cpi_items(
        "test-key", date(2024, 8, 1), date(2026, 8, 18), client=client
    )
    assert captured["key"] == "test-key"
    assert "series=TP.FG.J0" in captured["url"]
    assert "startDate=01-08-2024" in captured["url"]
    assert "endDate=18-08-2026" in captured["url"]
    assert items == [{"Tarih": "2025-6", "TP_FG_J0": "2915.27"}]


def test_fetch_raises_on_403():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(httpx.HTTPStatusError):
        ingest.fetch_cpi_items("bad", date(2024, 8, 1), date(2026, 8, 18), client=client)
