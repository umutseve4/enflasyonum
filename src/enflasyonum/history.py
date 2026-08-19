"""Harcama geçmişi grafiği (SVG) — M2.3.

Neden SVG? Kartla (M2.2) aynı gerekçe: grafik sunucu tarafında saf
string olarak, sıfır ek bağımlılıkla üretilir (matplotlib yok — Render
free build hafif kalır) ve testte string üzerinde doğrulanır.

Neden aylık toplama Python'da? Testler SQLite'ta, üretim PostgreSQL'de
koşar; ay bazlı SQL toplaması (date_trunc / strftime) iki motorda
farklı yazılır. Kişisel kullanım ölçeğinde satır sayısı küçük olduğu
için satırları çekip Python'da (yıl, ay) anahtarıyla toplamak hem
taşınabilir hem birim-testli. Para daima Decimal — asla float.
"""

from datetime import date
from decimal import Decimal
from xml.sax.saxutils import escape

#: Grafik boyutu — kartla aynı genişlik, ana sayfaya gömülür.
WIDTH = 800
HEIGHT = 360

#: Gösterilecek en fazla ay sayısı (son 12 ay).
MAX_MONTHS = 12

_MARGIN = 40
_CHART_TOP = 96
_CHART_BOTTOM = HEIGHT - 64


def monthly_totals(rows: list[tuple[date, Decimal]]) -> list[tuple[date, Decimal]]:
    """(spent_at, amount) satırlarını ay bazında topla.

    Dönüş: dönem sırasına göre ``[(ayın ilk günü, toplam)]`` — en fazla
    son ``MAX_MONTHS`` ay.
    """
    acc: dict[date, Decimal] = {}
    for spent_at, amount in rows:
        key = date(spent_at.year, spent_at.month, 1)
        acc[key] = acc.get(key, Decimal("0")) + Decimal(amount)
    return sorted(acc.items())[-MAX_MONTHS:]


def _svg_open() -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
        f'viewBox="0 0 {WIDTH} {HEIGHT}" role="img" '
        'aria-label="Aylık harcama geçmişi grafiği">\n'
        f'  <rect width="{WIDTH}" height="{HEIGHT}" rx="24" fill="#101418"/>\n'
    )


def render_history_svg(totals: list[tuple[date, Decimal]], version: str) -> str:
    """Aylık toplamlardan çubuk grafik SVG üret.

    ``totals`` boşsa Türkçe ipucu kartı döner — endpoint hiçbir koşulda
    500 vermez (kart ve ana sayfayla aynı ilke). Metinler XML'e karşı
    escape edilir.
    """
    parts = [_svg_open()]
    parts.append(
        '  <text x="40" y="56" fill="#8ab4f8" font-family="system-ui, sans-serif" '
        'font-size="24" font-weight="700">Harcama geçmişi</text>\n'
    )

    if not totals:
        parts.append(
            '  <text x="40" y="190" fill="#e8eaed" font-family="system-ui, sans-serif" '
            'font-size="22">Henüz harcama yok — grafik ilk kayıtla birlikte oluşur.</text>\n'
        )
    else:
        max_total = max(total for _, total in totals)
        chart_w = WIDTH - 2 * _MARGIN
        chart_h = _CHART_BOTTOM - _CHART_TOP
        slot = chart_w / len(totals)
        bar_w = slot * 0.6
        for i, (period, total) in enumerate(totals):
            ratio = float(total / max_total) if max_total > 0 else 0.0
            bar_h = max(int(chart_h * ratio), 2)
            x = _MARGIN + i * slot + (slot - bar_w) / 2
            y = _CHART_BOTTOM - bar_h
            cx = _MARGIN + i * slot + slot / 2
            parts.append(
                f'  <rect class="bar" x="{x:.1f}" y="{y}" width="{bar_w:.1f}" '
                f'height="{bar_h}" rx="4" fill="#8ab4f8"/>\n'
            )
            parts.append(
                f'  <text x="{cx:.1f}" y="{y - 8}" fill="#e8eaed" text-anchor="middle" '
                f'font-family="system-ui, sans-serif" font-size="14">'
                f"{escape(f'{total} TL')}</text>\n"
            )
            parts.append(
                f'  <text x="{cx:.1f}" y="{_CHART_BOTTOM + 22}" fill="#9aa0a6" '
                'text-anchor="middle" font-family="system-ui, sans-serif" font-size="13">'
                f"{escape(period.strftime('%Y-%m'))}</text>\n"
            )

    parts.append(
        f'  <text x="40" y="{HEIGHT - 20}" fill="#5f6368" '
        f'font-family="system-ui, sans-serif" font-size="14">'
        f"enflasyonum v{escape(version)}</text>\n"
    )
    parts.append("</svg>\n")
    return "".join(parts)
