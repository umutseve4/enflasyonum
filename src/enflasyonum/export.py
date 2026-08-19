"""CSV dışa aktarma (M3.1).

Harcamaları CSV metnine çevirir. Saf string üretimi: stdlib ``csv`` +
``io.StringIO``, yeni bağımlılık yok (SVG'lerdeki saf-string ilkesiyle
aynı gerekçe). Tutarlar Decimal olarak ``str()``'e çevrilir — float'a
asla dönüştürülmez (ikili kayan nokta yuvarlama hatası riski).

Parquet bilinçli olarak ertelendi: pyarrow bağımlılığı Render free-tier
build disiplinine aykırı (ROADMAP karar kaydı).
"""

import csv
import io
from collections.abc import Iterable, Sequence

#: CSV kolon başlıkları — aksansız ASCII: başlık satırı her araçta sorunsuz
#: parse edilsin; Türkçe karakterler veri satırlarında serbest.
CSV_HEADER = ("tarih", "kategori", "aciklama", "tutar")


def expenses_to_csv(rows: Iterable[Sequence]) -> str:
    """``(spent_at, kategori, aciklama, tutar)`` satırlarını CSV'ye çevirir.

    - Tarih ISO 8601 (``YYYY-AA-GG``)
    - Tutar ``Decimal`` -> ``str``, nokta ondalıklı (``"42.50"``)
    - Virgül/tırnak/yeni satır içeren alanları ``csv`` modülü RFC 4180'e
      göre escape eder
    - Boş girdi -> yalnız başlık satırı (asla boş string değil)
    """
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\r\n")
    writer.writerow(CSV_HEADER)
    for spent_at, category, description, amount in rows:
        writer.writerow([spent_at.isoformat(), category, description, str(amount)])
    return buf.getvalue()
