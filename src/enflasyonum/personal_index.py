"""Kişisel enflasyon endeksi — Laspeyres hesap motoru (M1.5).

Tasarım kararı (2026-08-18): harcama kaydında miktar/birim fiyat yok, yalnız
tutar var. Bu yüzden "kişisel endeks", kullanıcının BAZ dönemdeki kategori
harcama paylarının resmi fiyat görelileriyle ağırlıklı ortalamasıdır —
klasik Laspeyres formülünün harcama-ağırlıklı biçimi (ONS/Eurostat kişisel
enflasyon hesaplayıcılarıyla aynı yöntem):

    L_t = 100 * Σ(w_i * R_i) / Σ(w_i)

    w_i : baz dönemde i kategorisine yapılan harcama (TL)
    R_i : i kategorisinin fiyat görelisi = I_i,t / I_i,0

M2.1 itibarıyla ECOICOP alt endeksleri (EVDS ``bie_tukfiy2025`` grubu)
kategori görelilerini sağlar: ``category_relatives_from_db`` kategori adını
alt seriye eşler (``enflasyonum.series``), verisi olan kategoriler kendi
görelisini kullanır. Eşleşmeyen ya da verisi eksik her kategori manşet
göreliye düşer — motor kodu (``laspeyres``) değişmeden kalmıştır.

Ek karar (M1.6): resmi TÜFE ~1 ay geriden yayımlanır; kullanıcı bugün
harcama girer ama son resmi dönem geçmiştedir. ``weights_period`` parametresi
sepet ayını fiyat penceresinden ayırır: ağırlıklar kullanıcının güncel
sepetinden, fiyat görelisi resmi verinin kapsadığı pencereden gelir.

Tüm aritmetik ``Decimal`` ile yapılır (float yasak — karar kaydı: float
yuvarlama hatası enflasyon hesabını bozar).
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Iterable, Mapping

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from enflasyonum.models import Category, Expense, OfficialCPI
from enflasyonum.series import HEADLINE_SERIES, category_to_series

#: Endeks çıktısı 6 ondalığa yuvarlanır — official_cpi.index_value ile aynı
#: hassasiyet (bkz. migration 0002).
PRECISION = Decimal("0.000001")


class PersonalIndexError(ValueError):
    """Hesap için gerekli veri eksik ya da geçersiz."""


@dataclass(frozen=True)
class PersonalIndexResult:
    """Tek bir kişisel endeks hesabının sonucu ve girdi izi.

    ``weights`` ve ``relatives`` sonuçla birlikte taşınır ki M1.6 ekranı
    "bu sayı nereden geldi?" sorusunu hesap tekrarı yapmadan gösterebilsin.
    """

    base_period: date
    current_period: date
    index_value: Decimal  # baz dönem = 100
    weights: dict[str, Decimal] = field(default_factory=dict)
    relatives: dict[str, Decimal] = field(default_factory=dict)

    @property
    def inflation_pct(self) -> Decimal:
        """Baz döneme göre yüzde değişim (endeks - 100)."""
        return self.index_value - Decimal(100)


def laspeyres(
    weights: Mapping[str, Decimal], relatives: Mapping[str, Decimal]
) -> Decimal:
    """Saf Laspeyres çekirdeği: ağırlıklı fiyat görelisi ortalaması.

    DB'ye dokunmaz; tek başına test edilebilir. ``weights`` baz dönem
    harcamaları (TL), ``relatives`` kategori başına I_t/I_0 oranıdır.
    Dönüş: baz dönem = 100 olan endeks değeri, 6 ondalığa yuvarlı.
    """
    if not weights:
        raise PersonalIndexError("agirlik yok: baz donemde hic harcama bulunamadi")

    total = Decimal(0)
    weighted_sum = Decimal(0)
    for cat, w in weights.items():
        if w < 0:
            raise PersonalIndexError(f"negatif agirlik: {cat}={w}")
        if cat not in relatives:
            raise PersonalIndexError(f"fiyat gorelisi eksik: {cat}")
        total += w
        weighted_sum += w * relatives[cat]

    if total == 0:
        raise PersonalIndexError("toplam agirlik sifir: endeks tanimsiz")

    return (Decimal(100) * weighted_sum / total).quantize(PRECISION)


def _month_bounds(period: date) -> tuple[date, date]:
    last_day = calendar.monthrange(period.year, period.month)[1]
    return (
        date(period.year, period.month, 1),
        date(period.year, period.month, last_day),
    )


def category_weights(session: Session, period: date) -> dict[str, Decimal]:
    """Baz ayın kategori bazlı harcama toplamları (kategori adı -> TL)."""
    start, end = _month_bounds(period)
    rows = session.execute(
        select(Category.name, func.sum(Expense.amount))
        .join(Expense, Expense.category_id == Category.id)
        .where(Expense.spent_at.between(start, end))
        .group_by(Category.name)
    ).all()
    return {name: Decimal(str(total)) for name, total in rows}


def _official_index(
    session: Session, period: date, series_code: str = HEADLINE_SERIES
) -> Decimal:
    row = session.scalar(
        select(OfficialCPI).where(
            OfficialCPI.period == date(period.year, period.month, 1),
            OfficialCPI.series_code == series_code,
        )
    )
    if row is None:
        raise PersonalIndexError(
            f"official_cpi'da {period.year}-{period.month:02d} donemi yok "
            "(once ingest calistir)"
        )
    return Decimal(str(row.index_value))


def headline_relative(session: Session, base: date, current: date) -> Decimal:
    """Manşet TÜFE fiyat görelisi: I_current / I_base (official_cpi'dan)."""
    base_value = _official_index(session, base)
    if base_value == 0:
        raise PersonalIndexError("baz donem endeksi sifir: goreli tanimsiz")
    return _official_index(session, current) / base_value


def series_relative(
    session: Session, base: date, current: date, series_code: str
) -> Decimal | None:
    """Alt endeks fiyat görelisi: I_current / I_base (verilen seri için).

    Veri eksikse ya da baz değer sıfırsa None döner — çağıran manşete
    düşer; hesap bu yüzden asla patlamaz (M2.1 kararı: alt seri henüz
    ingest edilmediyse davranış M1 ile birebir aynı kalır).
    """
    try:
        base_value = _official_index(session, base, series_code)
        current_value = _official_index(session, current, series_code)
    except PersonalIndexError:
        return None
    if base_value == 0:
        return None
    return current_value / base_value


def category_relatives_from_db(
    session: Session, base: date, current: date, categories: Iterable[str]
) -> dict[str, Decimal]:
    """Kategori -> alt endeks görelisi sözlüğü (M2.1).

    Eşleşmeyen kategori ya da verisi eksik seri sözlüğe girmez; motor o
    kategoriler için manşet göreliyi kullanır (mevcut fallback davranışı).
    """
    out: dict[str, Decimal] = {}
    for cat in categories:
        code = category_to_series(cat)
        if code is None:
            continue
        rel = series_relative(session, base, current, code)
        if rel is not None:
            out[cat] = rel
    return out


def compute_personal_index(
    session: Session,
    *,
    base: date,
    current: date,
    category_relatives: Mapping[str, Decimal] | None = None,
    weights_period: date | None = None,
) -> PersonalIndexResult:
    """Uçtan uca hesap: DB'den ağırlıklar + göreliler -> Laspeyres endeksi.

    ``category_relatives`` verilirse (M2: ECOICOP alt endeks görelileri)
    eşleşen kategoriler onu kullanır; verilmeyen her kategori manşet TÜFE
    görelisine düşer (M1 davranışı: tüm kategoriler manşete düşer).

    ``weights_period`` verilirse sepet ağırlıkları o aydan alınır; fiyat
    penceresi (``base`` -> ``current``) değişmez. M1.6 kullanımı: resmi
    TÜFE geriden yayımlandığı için sepet = kullanıcının son harcama ayı,
    pencere = resmi verinin son 12 ayı. Verilmezse klasik davranış:
    sepet ayı = baz ay.
    """
    basket = weights_period or base
    weights = category_weights(session, basket)
    if not weights:
        raise PersonalIndexError(
            f"{basket.year}-{basket.month:02d} doneminde hic harcama yok"
        )

    headline = headline_relative(session, base, current)
    provided = dict(category_relatives or {})
    relatives = {cat: provided.get(cat, headline) for cat in weights}

    return PersonalIndexResult(
        base_period=date(base.year, base.month, 1),
        current_period=date(current.year, current.month, 1),
        index_value=laspeyres(weights, relatives),
        weights=weights,
        relatives=relatives,
    )
