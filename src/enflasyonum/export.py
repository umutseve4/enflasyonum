"""CSV dışa aktarma (M3.1).

Harcamaları CSV metnine çevirir. Saf string üretimi: stdlib ``csv`` +
``io.StringIO``, yeni bağımlılık yok (SVG'lerdeki saf-string ilkesiyle
aynı gerekçe). Tutarlar Decimal olarak ``str()``'e çevrilir — float'a
asla dönüştürülmez (ikili kayan nokta yuvarlama hatası riski).

Güvenlik — CSV injection: Excel/LibreOffice, ``=``, ``+``, ``-``, ``@``
(ve TAB/CR) ile başlayan hücreleri formül olarak yürütebilir. Kullanıcı
kontrollü serbest metinler (kategori, açıklama) hücre başına ``'``
önekiyle nötralize edilir. Tarih (ISO 8601) ve tutar (uygulamanın
pozitif zorladığı Decimal) serbest metin olmadığından defuse edilmez —
sayısal kolonlar bozulmaz.

Parquet bilinçli olarak ertelendi: pyarrow bağımlılığı Render free-tier
build disiplinine aykırı (ROADMAP karar kaydı).
"""

import csv
import io
from collections.abc import Iterable, Sequence

#: CSV kolon başlıkları — aksansız ASCII: başlık satırı her araçta sorunsuz
#: parse edilsin; Türkçe karakterler veri satırlarında serbest.
CSV_HEADER = ("tarih", "kategori", "aciklama", "tutar")

#: Bu karakterlerle başlayan hücre, elektronik tablo yazılımında formül
#: olarak yürütülebilir (CSV/formula injection — OWASP).
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _defuse(value: str) -> str:
    """Formül önekli hücreyi ``'`` ile nötralize eder (CSV injection savunması)."""
    return f"'{value}" if value.startswith(_FORMULA_PREFIXES) else value


def expenses_to_csv(rows: Iterable[Sequence]) -> str:
    """``(spent_at, kategori, aciklama, tutar)`` satırlarını CSV'ye çevirir.

    - Tarih ISO 8601 (``YYYY-AA-GG``)
    - Tutar ``Decimal`` -> ``str``, nokta ondalıklı (``"42.50"``)
    - Virgül/tırnak/yeni satır içeren alanları ``csv`` modülü RFC 4180'e
      göre escape eder
    - Kategori ve açıklama formül öneklerine karşı nötralize edilir
    - Boş girdi -> yalnız başlık satırı (asla boş string değil)
    """
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\r\n")
    writer.writerow(CSV_HEADER)
    for spent_at, category, description, amount in rows:
        writer.writerow(
            [spent_at.isoformat(), _defuse(category), _defuse(description), str(amount)]
        )
    return buf.getvalue()
