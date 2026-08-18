"""ECOICOP (2025=100) seri kodları ve kategori → alt endeks eşleme tablosu (M2.1).

TÜİK 2025=100 TÜFE'si 13 ana ECOICOP bölümü yayımlar (EVDS grubu
``bie_tukfiy2025``): manşet ``TP.TUKFIY2025.GENEL`` + ``TP.TUKFIY2025.01`` ..
``TP.TUKFIY2025.13``. Kullanıcının serbest metin kategorisi buradaki anahtar
sözlüğüyle bir bölüme eşlenir; eşleşmeyen kategori manşet TÜFE'ye düşer
(personal_index motorundaki mevcut fallback davranışı, motor değişmez).

Karar kaydı (2026-08-19): eşleme KATEGORİ ADI üzerinden ve TAM eşleşmeyle
yapılır (substring değil) — "su" gibi kısa anahtarların yanlış bölüme
kaçmasını önler. Bilinmeyen kategori sessizce manşete düşer; ekranda
yıldızla (*) işaretlenir ki kullanıcı eşleşmediğini görsün.
"""

from __future__ import annotations

SERIES_PREFIX = "TP.TUKFIY2025."
HEADLINE_SERIES = "TP.TUKFIY2025.GENEL"

#: 13 ana ECOICOP bölümü (EVDS ``bie_tukfiy2025`` grubundaki resmi adlar).
DIVISIONS: dict[str, str] = {
    "01": "Gıda Ve Alkolsüz İçecekler",
    "02": "Alkollü İçecekler Ve Tütün",
    "03": "Giyim Ve Ayakkabı",
    "04": "Konut, Su, Elektrik, Gaz Ve Diğer Yakıtlar",
    "05": "Mobilya, Ev Aletleri Ve Ev Bakım Hizmetleri",
    "06": "Sağlık",
    "07": "Ulaştırma",
    "08": "Bilgi Ve İletişim",
    "09": "Eğlence, Dinlence, Spor Ve Kültür",
    "10": "Eğitim Hizmetleri",
    "11": "Lokantalar Ve Konaklama Hizmetleri",
    "12": "Sigorta Ve Finansal Hizmetler",
    "13": "Kişisel Bakım, Sosyal Koruma Ve Çeşitli Mal Ve Hizmetler",
}

#: Manşet + 13 bölüm — ingest bu listenin tamamını çeker (14 seri).
ALL_SERIES: list[str] = [HEADLINE_SERIES] + [SERIES_PREFIX + code for code in DIVISIONS]

#: Normalize kategori adı -> bölüm kodu. Tam eşleşme; anahtarlar küçük harf.
#: Türkçe ve ASCII yazımlar bilinçli olarak çift tutulur (gıda/gida).
CATEGORY_TO_DIVISION: dict[str, str] = {
    # 01 — Gıda Ve Alkolsüz İçecekler
    "gıda": "01",
    "gida": "01",
    "market": "01",
    "yiyecek": "01",
    "içecek": "01",
    "icecek": "01",
    # 02 — Alkollü İçecekler Ve Tütün
    "alkol": "02",
    "tütün": "02",
    "tutun": "02",
    "sigara": "02",
    # 03 — Giyim Ve Ayakkabı
    "giyim": "03",
    "kıyafet": "03",
    "kiyafet": "03",
    "ayakkabı": "03",
    "ayakkabi": "03",
    # 04 — Konut, Su, Elektrik, Gaz Ve Diğer Yakıtlar
    "konut": "04",
    "kira": "04",
    "elektrik": "04",
    "su": "04",
    "doğalgaz": "04",
    "dogalgaz": "04",
    "fatura": "04",
    # 05 — Mobilya, Ev Aletleri Ve Ev Bakım Hizmetleri
    "mobilya": "05",
    "ev eşyası": "05",
    "ev esyasi": "05",
    # 06 — Sağlık
    "sağlık": "06",
    "saglik": "06",
    "ilaç": "06",
    "ilac": "06",
    "eczane": "06",
    # 07 — Ulaştırma
    "ulaşım": "07",
    "ulasim": "07",
    "benzin": "07",
    "akaryakıt": "07",
    "akaryakit": "07",
    "akbil": "07",
    "taksi": "07",
    "otobüs": "07",
    "otobus": "07",
    # 08 — Bilgi Ve İletişim
    "iletişim": "08",
    "iletisim": "08",
    "internet": "08",
    "telefon": "08",
    # 09 — Eğlence, Dinlence, Spor Ve Kültür
    "eğlence": "09",
    "eglence": "09",
    "spor": "09",
    "sinema": "09",
    "kültür": "09",
    "kultur": "09",
    "kitap": "09",
    "oyun": "09",
    # 10 — Eğitim Hizmetleri
    "eğitim": "10",
    "egitim": "10",
    "okul": "10",
    "kurs": "10",
    # 11 — Lokantalar Ve Konaklama Hizmetleri
    "lokanta": "11",
    "restoran": "11",
    "kafe": "11",
    "cafe": "11",
    "otel": "11",
    # 12 — Sigorta Ve Finansal Hizmetler
    "sigorta": "12",
    "banka": "12",
    "finans": "12",
    # 13 — Kişisel Bakım, Sosyal Koruma Ve Çeşitli Mal Ve Hizmetler
    "kozmetik": "13",
    "kişisel bakım": "13",
    "kisisel bakim": "13",
    "kuaför": "13",
    "kuafor": "13",
    "berber": "13",
}


def division_series(code: str) -> str:
    """Bölüm kodu ('01'..'13') -> EVDS seri kodu."""
    return SERIES_PREFIX + code


def json_key(series_code: str) -> str:
    """EVDS JSON çıktısında seri kodundaki noktalar alt çizgiye döner."""
    return series_code.replace(".", "_")


def category_to_series(name: str) -> str | None:
    """Kategori adını alt endeks seri koduna eşle; eşleşme yoksa None.

    None = manşet TÜFE fallback'i (personal_index motoru değişmeden kalır).
    """
    code = CATEGORY_TO_DIVISION.get(name.strip().lower())
    if code is None:
        return None
    return division_series(code)
