"""M3.2 latest_headline_marker + run() marker sözleşmesi testleri."""

import os
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from enflasyonum import ingest
from enflasyonum.series import json_key


def row(y, m, value):
    return SimpleNamespace(period=date(y, m, 1), index_value=Decimal(value))


def test_marker_empty_rows():
    assert ingest.latest_headline_marker([]) == (None, None)


def test_marker_single_row_no_pct():
    period, pct = ingest.latest_headline_marker([row(2026, 7, "100")])
    assert period == date(2026, 7, 1)
    assert pct is None


def test_marker_consecutive_months_pct():
    rows = [row(2026, 6, "100"), row(2026, 7, "102.5")]
    assert ingest.latest_headline_marker(rows) == (date(2026, 7, 1), Decimal("2.50"))


def test_marker_gap_month_no_pct():
    """QA bulgu 3: arada ay eksikse oran aylık TÜFE değildir → pct=None."""
    rows = [row(2026, 5, "100"), row(2026, 7, "104")]
    period, pct = ingest.latest_headline_marker(rows)
    assert period == date(2026, 7, 1)
    assert pct is None


def test_marker_year_boundary():
    """Aralık → Ocak geçişi ardışık sayılır."""
    rows = [row(2025, 12, "200"), row(2026, 1, "206.13")]
    assert ingest.latest_headline_marker(rows) == (date(2026, 1, 1), Decimal("3.07"))


def test_marker_zero_prev_index_no_pct():
    """QA sağlamlaştırma: önceki endeks <= 0 ise bölme yapılmaz."""
    rows = [row(2026, 6, "0"), row(2026, 7, "102")]
    period, pct = ingest.latest_headline_marker(rows)
    assert period == date(2026, 7, 1)
    assert pct is None


def test_marker_rounding_half_up():
    rows = [row(2026, 6, "100"), row(2026, 7, "102.005")]
    _, pct = ingest.latest_headline_marker(rows)
    assert pct == Decimal("2.01")  # 2.005 → HALF_UP → 2.01


@pytest.fixture()
def migrated_engine(tmp_path, monkeypatch):
    url = os.environ.get("DATABASE_URL") or f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")
    engine = create_engine(url)
    yield engine
    engine.dispose()
    command.downgrade(cfg, "base")


def _fake_fetch_two_months(api_key, start, end, series_code=ingest.SERIES, client=None):
    key = json_key(series_code)
    return [
        {"Tarih": "2026-6", key: "100"},
        {"Tarih": "2026-7", key: "102.5"},
    ]


def test_run_pass_prints_markers(migrated_engine, monkeypatch, capsys):
    """QA bulgu 6.1: başarılı koşuda stdout marker sözleşmesi."""
    monkeypatch.setenv("EVDS_API_KEY", "test-key")
    monkeypatch.setattr(ingest, "fetch_cpi_items", _fake_fetch_two_months)
    monkeypatch.setattr(
        ingest, "create_session_factory", lambda: sessionmaker(bind=migrated_engine)
    )
    assert ingest.run(2) == 0
    out = capsys.readouterr().out
    assert "HEADLINE_LATEST_PERIOD=2026-07" in out
    assert "HEADLINE_MOM_PCT=2.50" in out


def test_run_fail_prints_no_marker(migrated_engine, monkeypatch, capsys):
    """QA bulgu 6.3: eksik seri → FAIL → marker basılmaz."""
    monkeypatch.setenv("EVDS_API_KEY", "test-key")

    def fake_fetch(api_key, start, end, series_code=ingest.SERIES, client=None):
        if series_code.endswith(".13"):
            return []  # bir alt seri eksik → FAIL
        return _fake_fetch_two_months(api_key, start, end, series_code, client)

    monkeypatch.setattr(ingest, "fetch_cpi_items", fake_fetch)
    monkeypatch.setattr(
        ingest, "create_session_factory", lambda: sessionmaker(bind=migrated_engine)
    )
    assert ingest.run(2) == 1
    out = capsys.readouterr().out
    assert "HEADLINE_LATEST_PERIOD" not in out
    assert "sonuc: FAIL" in out
