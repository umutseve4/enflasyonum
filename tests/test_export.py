"""M3.1 /export.csv testleri: saf CSV üretimi + HTTP sözleşmesi."""

import os
from datetime import date
from decimal import Decimal

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from enflasyonum.export import CSV_HEADER, expenses_to_csv
from enflasyonum.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    url = os.environ.get("DATABASE_URL") or f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")
    with TestClient(app) as c:
        yield c
    command.downgrade(cfg, "base")


# --- saf fonksiyon ---


def test_header_tuple_stable():
    assert CSV_HEADER == ("tarih", "kategori", "aciklama", "tutar")


def test_empty_rows_header_only():
    assert expenses_to_csv([]) == "tarih,kategori,aciklama,tutar\r\n"


def test_rows_serialized_in_order():
    rows = [
        (date(2026, 8, 1), "gıda", "süt", Decimal("42.50")),
        (date(2026, 8, 2), "ulaşım", "otobüs", Decimal("15.00")),
    ]
    lines = expenses_to_csv(rows).splitlines()
    assert lines[0] == "tarih,kategori,aciklama,tutar"
    assert lines[1] == "2026-08-01,gıda,süt,42.50"
    assert lines[2] == "2026-08-02,ulaşım,otobüs,15.00"


def test_decimal_trailing_zero_preserved():
    # float'a çevrilseydi "0.1" görürdük; Decimal str'i ondalığı korur.
    out = expenses_to_csv([(date(2026, 8, 1), "gıda", "x", Decimal("0.10"))])
    assert "0.10" in out


def test_comma_and_quote_escaped():
    out = expenses_to_csv(
        [(date(2026, 8, 1), "gıda", 'süt, "tam yağlı"', Decimal("1.00"))]
    )
    # RFC 4180: alan tırnaklanır, iç tırnak ikilenir.
    assert '"süt, ""tam yağlı"""' in out


def test_newline_in_description_escaped():
    out = expenses_to_csv(
        [(date(2026, 8, 1), "gıda", "satır1\nsatır2", Decimal("1.00"))]
    )
    assert '"satır1\nsatır2"' in out


# --- HTTP sözleşmesi ---


def test_export_empty_db_header_only(client):
    r = client.get("/export.csv")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    assert "enflasyonum-harcamalar.csv" in r.headers["content-disposition"]
    assert r.headers["cache-control"] == "no-store"
    assert r.text.lstrip("\ufeff") == "tarih,kategori,aciklama,tutar\r\n"


def test_export_starts_with_utf8_bom(client):
    # Excel-TR, BOM'suz UTF-8 CSV'de Türkçe karakterleri bozuyor.
    r = client.get("/export.csv")
    assert r.content.startswith(b"\xef\xbb\xbf")


def test_export_contains_posted_expense(client):
    client.post(
        "/expenses",
        data={
            "description": "süt",
            "amount": "42,50",
            "category": "gıda",
            "spent_at": "2026-08-18",
        },
        follow_redirects=False,
    )
    r = client.get("/export.csv")
    assert "2026-08-18,gıda,süt,42.50" in r.text


def test_export_rows_sorted_by_date(client):
    for d, desc in [("2026-08-19", "ikinci"), ("2026-08-01", "ilk")]:
        client.post(
            "/expenses",
            data={
                "description": desc,
                "amount": "10",
                "category": "test",
                "spent_at": d,
            },
            follow_redirects=False,
        )
    body = client.get("/export.csv").text
    assert body.index("ilk") < body.index("ikinci")
