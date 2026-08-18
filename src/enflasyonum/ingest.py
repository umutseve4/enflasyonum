"""TÜİK TÜFE verisini TCMB EVDS API'sinden çekip DB'ye yazan ingestion job'ı.

Kaynak: EVDS web servisi (evds3.tcmb.gov.tr), seri: TP.TUKFIY2025.GENEL
(Tüketici Fiyat Endeksi, 2025=100, aylık; grup bie_tukfiy2025).

Not: TÜİK, Ocak 2026'dan itibaren TÜFE temel yılını 2003=100'den
2025=100'e taşıdı (ECOICOP v2, AB uyumu). Eski seri TP.FG.J0 2026-01'de
kesildi. Yeni seri geçmişe dönük değerleri de içerir; zincirleme gerekmez.
Karar kaydı: ROADMAP.md.

Kurallar:
- API anahtarı `EVDS_API_KEY` ortam değişkeninden okunur, koda gömülmez.
- Anahtar HTTP header'da `key` olarak gönderilir (query'de değil — EVDS
  dokümantasyonu; yanlış/eksik anahtar 403 döner).
- Tarih formatı gg-aa-yyyy (EVDS zorunluluğu).
- Yazım `upsert_official_cpi` ile yapılır → job idempotent: aynı ayı
  ikinci kez çekmek satır çiftlemez, günceller.

Kullanım:
    EVDS_API_KEY=... python -m enflasyonum.ingest [ay_sayisi]
"""

from __future__ import annotations

import os
import sys
from datetime import date
from decimal import Decimal, InvalidOperation

import httpx
from sqlalchemy.orm import Session

from enflasyonum import crud
from enflasyonum.db import create_session_factory

EVDS_BASE = "https://evds3.tcmb.gov.tr/igmevdsms-dis/"
SERIES = "TP.TUKFIY2025.GENEL"
# EVDS JSON çıktısında seri kodundaki noktalar alt çizgiye döner.
SERIES_JSON_KEY = SERIES.replace(".", "_")


def months_back(today: date, months: int) -> date:
    """Bugünden `months` ay geriye git, o ayın ilk gününü döndür.

    EVDS aylık frekansta eksiksiz veri için başlangıç tarihinin ayın
    ilk günü olmasını şart koşar.
    """
    year = today.year
    month = today.month - months
    while month <= 0:
        month += 12
        year -= 1
    return date(year, month, 1)


def fetch_cpi_items(
    api_key: str,
    start: date,
    end: date,
    client: httpx.Client | None = None,
) -> list[dict]:
    """EVDS'den ham seri kayıtlarını çek. `client` testte mock transport için."""
    url = (
        f"{EVDS_BASE}series={SERIES}"
        f"&startDate={start.strftime('%d-%m-%Y')}"
        f"&endDate={end.strftime('%d-%m-%Y')}"
        "&type=json"
    )
    own_client = client is None
    c = client or httpx.Client(timeout=30)
    try:
        resp = c.get(url, headers={"key": api_key})
        resp.raise_for_status()
        payload = resp.json()
    finally:
        if own_client:
            c.close()
    return payload.get("items", [])


def parse_period(raw: str) -> date:
    """EVDS aylık 'Tarih' alanı ('2024-1' veya '1-2024') -> ayın ilk günü."""
    a, b = raw.strip().split("-")
    if len(a) == 4:
        year, month = int(a), int(b)
    else:
        year, month = int(b), int(a)
    return date(year, month, 1)


def parse_items(items: list[dict]) -> list[tuple[date, Decimal]]:
    """Ham kayıtları (dönem, endeks) çiftlerine çevir; boş/bozuk değerleri atla.

    Para/endeks değerleri Decimal'e string üzerinden gider — float'a
    uğramaz (yuvarlama hatası yasağı, bkz. ROADMAP karar kaydı).
    """
    out: list[tuple[date, Decimal]] = []
    for item in items:
        raw_value = item.get(SERIES_JSON_KEY)
        raw_period = item.get("Tarih")
        if raw_value is None or raw_period is None:
            continue
        try:
            period = parse_period(str(raw_period))
            value = Decimal(str(raw_value))
        except (ValueError, InvalidOperation):
            continue
        out.append((period, value))
    return out


def ingest_cpi(session: Session, parsed: list[tuple[date, Decimal]]) -> int:
    """Upsert ile yaz; döndürülen sayı işlenen dönem sayısıdır."""
    for period, value in parsed:
        crud.upsert_official_cpi(session, period=period, index_value=value)
    return len(parsed)


def run(months: int = 24) -> int:
    """CLI girişi. 0 = PASS, 1 = FAIL döner."""
    api_key = os.environ.get("EVDS_API_KEY")
    if not api_key:
        print("FAIL: EVDS_API_KEY ortam değişkeni tanımlı değil.")
        print("Anahtar: https://evds3.tcmb.gov.tr → üye ol → Profilim → API Key.")
        return 1

    today = date.today()
    start = months_back(today, months)
    try:
        items = fetch_cpi_items(api_key, start, today)
    except httpx.HTTPError as exc:
        print(f"FAIL: EVDS isteği başarısız: {exc}")
        return 1

    parsed = parse_items(items)
    factory = create_session_factory()
    with factory() as session:
        n = ingest_cpi(session, parsed)
        rows = crud.list_official_cpi(session)

    print("===== OTOMATIK KONTROL =====")
    print(f"islenen donem: {n}")
    print(f"tablodaki satir: {len(rows)}")
    if rows:
        print(f"aralik: {rows[0].period} .. {rows[-1].period}")
    status = "PASS" if n >= min(months, 12) else "FAIL"
    print(f"sonuc: {status}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    n_months = int(sys.argv[1]) if len(sys.argv) > 1 else 24
    raise SystemExit(run(n_months))
