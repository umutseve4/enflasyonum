"""TÜİK TÜFE verisini TCMB EVDS API'sinden çekip DB'ye yazan ingestion job'ı.

Kaynak: EVDS web servisi (evds3.tcmb.gov.tr), grup bie_tukfiy2025
(Tüketici Fiyat Endeksi, 2025=100, aylık). M2.1'den itibaren manşet
(TP.TUKFIY2025.GENEL) + 13 ECOICOP bölüm endeksi (TP.TUKFIY2025.01..13)
birlikte çekilir — toplam 14 seri (liste: enflasyonum.series.ALL_SERIES).

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
- M3.2: her BAŞARILI koşu, DB'deki en son manşet dönemini makine-okur
  marker olarak basar (level-triggered). Bildirim katmanı (notify.py)
  idempotentliği kendisi sağlar; böylece geçici issue hatası ertesi gün
  otomatik yeniden denenir. Karar kaydı: ROADMAP.md.

Kullanım:
    EVDS_API_KEY=... python -m enflasyonum.ingest [ay_sayisi]
"""

from __future__ import annotations

import os
import sys
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

import httpx
from sqlalchemy.orm import Session

from enflasyonum import crud
from enflasyonum.db import create_session_factory
from enflasyonum.series import ALL_SERIES, HEADLINE_SERIES, json_key

EVDS_BASE = "https://evds3.tcmb.gov.tr/igmevdsms-dis/"
SERIES = HEADLINE_SERIES  # manşet; test test_series_is_2025_base bunu sabitler
# EVDS JSON çıktısında seri kodundaki noktalar alt çizgiye döner.
SERIES_JSON_KEY = json_key(SERIES)


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
    series_code: str = SERIES,
    client: httpx.Client | None = None,
) -> list[dict]:
    """EVDS'den ham seri kayıtlarını çek. `client` testte mock transport için."""
    url = (
        f"{EVDS_BASE}series={series_code}"
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


def parse_items(
    items: list[dict], value_key: str = SERIES_JSON_KEY
) -> list[tuple[date, Decimal]]:
    """Ham kayıtları (dönem, endeks) çiftlerine çevir; boş/bozuk değerleri atla.

    `value_key` seri başına değişir (M2.1) — varsayılan manşet anahtarı.
    Para/endeks değerleri Decimal'e string üzerinden gider — float'a
    uğramaz (yuvarlama hatası yasağı, bkz. ROADMAP karar kaydı).
    """
    out: list[tuple[date, Decimal]] = []
    for item in items:
        raw_value = item.get(value_key)
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


def ingest_cpi(
    session: Session, parsed: list[tuple[date, Decimal]], series_code: str = SERIES
) -> int:
    """Upsert ile yaz; döndürülen sayı işlenen dönem sayısıdır."""
    for period, value in parsed:
        crud.upsert_official_cpi(
            session, period=period, index_value=value, series_code=series_code
        )
    return len(parsed)


def latest_headline_marker(rows) -> tuple[date | None, Decimal | None]:
    """M3.2: son manşet dönemi + aylık değişim yüzdesi (koşullu).

    Aylık % yalnız sondan bir önceki satır TAM OLARAK bir önceki takvim
    ayı ise hesaplanır (arada ay eksikse iki dönemin oranı aylık TÜFE
    değildir — QA bulgu 3). Önceki endeks <= 0 ise bölme yapılmaz.
    Decimal ile hesap, 2 hane ROUND_HALF_UP; float yasağı geçerli.
    """
    if not rows:
        return None, None
    last = rows[-1]
    if len(rows) < 2:
        return last.period, None
    prev = rows[-2]
    prev_year, prev_month = last.period.year, last.period.month - 1
    if prev_month == 0:
        prev_year, prev_month = prev_year - 1, 12
    if prev.period != date(prev_year, prev_month, 1):
        return last.period, None
    prev_value = Decimal(str(prev.index_value))
    if prev_value <= 0:
        return last.period, None
    pct = (Decimal(str(last.index_value)) / prev_value - 1) * 100
    return last.period, pct.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def run(months: int = 24) -> int:
    """CLI girişi. 0 = PASS, 1 = FAIL döner. M2.1: 14 seriyi birden çeker."""
    api_key = os.environ.get("EVDS_API_KEY")
    if not api_key:
        print("FAIL: EVDS_API_KEY ortam değişkeni tanımlı değil.")
        print("Anahtar: https://evds3.tcmb.gov.tr → üye ol → Profilim → API Key.")
        return 1

    today = date.today()
    start = months_back(today, months)
    counts: dict[str, int] = {}
    factory = create_session_factory()
    try:
        with httpx.Client(timeout=30) as client, factory() as session:
            for code in ALL_SERIES:
                items = fetch_cpi_items(api_key, start, today, series_code=code, client=client)
                parsed = parse_items(items, value_key=json_key(code))
                counts[code] = ingest_cpi(session, parsed, series_code=code)
            rows = crud.list_official_cpi(session)
    except httpx.HTTPError as exc:
        print(f"FAIL: EVDS isteği başarısız: {exc}")
        return 1

    need = min(months, 12)
    eksik = [code for code, n in counts.items() if n < need]

    print("===== OTOMATIK KONTROL =====")
    print(f"islenen donem: {counts[SERIES]}")
    for code, n in counts.items():
        print(f"islenen {code}: {n}")
    print(f"tablodaki satir (manset): {len(rows)}")
    if rows:
        print(f"aralik: {rows[0].period} .. {rows[-1].period}")
    if eksik:
        print(f"eksik seriler: {', '.join(eksik)}")
    status = "PASS" if not eksik else "FAIL"
    print(f"sonuc: {status}")
    if status == "PASS":
        # M3.2: level-triggered marker — bildirim katmanı (notify.py) okur.
        period, pct = latest_headline_marker(rows)
        if period is not None:
            print(f"HEADLINE_LATEST_PERIOD={period:%Y-%m}")
            if pct is not None:
                print(f"HEADLINE_MOM_PCT={pct}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    n_months = int(sys.argv[1]) if len(sys.argv) > 1 else 24
    raise SystemExit(run(n_months))
