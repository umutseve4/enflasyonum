"""Paylaşılabilir aylık özet kartı (SVG) — M2.2.

Neden SVG? Render free planında matplotlib gibi ağır bağımlılıklar
gereksiz; SVG sunucu tarafında saf string olarak, sıfır ek bağımlılıkla
üretilir, testte string üzerinde doğrulanır ve her sosyal platformda
tarayıcıda açılır. Boyut 800x418 (yaklaşık 1.91:1 — sosyal medya kart
oranı).

Girdi ``_comparison_context`` çıktısıdır; veri eksikse ipucu kartı
üretilir — endpoint hiçbir koşulda 500 vermez (ana sayfayla aynı ilke).
"""

from decimal import Decimal
from xml.sax.saxutils import escape

#: Kart boyutu — sosyal medya paylaşım oranına yakın.
WIDTH = 800
HEIGHT = 418

#: Dökümde gösterilecek en büyük N kategori.
TOP_CATEGORIES = 3


def _fmt_pct(value: Decimal) -> str:
    """Decimal -> '%%23.05' gösterimi (işaretsiz, template ile tutarlı)."""
    return f"%{value}"


def _fmt_diff(value: Decimal) -> str:
    """Fark her zaman işaretli: '+8.70' / '-3.10' / '+0.00'."""
    sign = "+" if value >= 0 else ""
    return f"{sign}{value}"


def _svg_open() -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
        f'viewBox="0 0 {WIDTH} {HEIGHT}" role="img" '
        'aria-label="Kişisel enflasyon özet kartı">\n'
        f'  <rect width="{WIDTH}" height="{HEIGHT}" rx="24" fill="#101418"/>\n'
    )


def render_card_svg(
    comparison: dict | None, hint: str | None, version: str
) -> str:
    """Kıyas verisinden paylaşılabilir SVG kart üret.

    ``comparison`` None ise ``hint`` metniyle bilgilendirme kartı döner;
    kullanıcı metinleri (kategori adları, ipucu) XML'e karşı escape edilir.
    """
    parts = [_svg_open()]
    parts.append(
        '  <text x="40" y="64" fill="#8ab4f8" font-family="system-ui, sans-serif" '
        'font-size="28" font-weight="700">Enflasyonumdan ne haber?</text>\n'
    )

    if comparison is None:
        message = escape(hint or "Kıyas için yeterli veri yok.")
        parts.append(
            f'  <text x="40" y="210" fill="#e8eaed" font-family="system-ui, sans-serif" '
            f'font-size="24">{message}</text>\n'
        )
    else:
        personal = _fmt_pct(comparison["personal_pct"])
        official = _fmt_pct(comparison["official_pct"])
        diff = _fmt_diff(comparison["diff_pct"])
        window = (
            f"{comparison['base_period'].strftime('%Y-%m')} → "
            f"{comparison['current_period'].strftime('%Y-%m')}"
        )
        basket = comparison["basket_period"].strftime("%Y-%m")

        # İki büyük sayı: senin vs resmi.
        parts.append(
            '  <text x="40" y="130" fill="#9aa0a6" font-family="system-ui, sans-serif" '
            'font-size="20">Senin enflasyonun</text>\n'
            f'  <text x="40" y="196" fill="#f28b82" font-family="system-ui, sans-serif" '
            f'font-size="56" font-weight="800">{escape(personal)}</text>\n'
            '  <text x="420" y="130" fill="#9aa0a6" font-family="system-ui, sans-serif" '
            'font-size="20">Resmi TÜFE (TÜİK)</text>\n'
            f'  <text x="420" y="196" fill="#8ab4f8" font-family="system-ui, sans-serif" '
            f'font-size="56" font-weight="800">{escape(official)}</text>\n'
            f'  <text x="40" y="244" fill="#e8eaed" font-family="system-ui, sans-serif" '
            f'font-size="22">Fark: {escape(diff)} puan</text>\n'
            f'  <text x="40" y="278" fill="#9aa0a6" font-family="system-ui, sans-serif" '
            f'font-size="16">Fiyat penceresi: {escape(window)} · '
            f'Sepet: {escape(basket)} harcamaların</text>\n'
        )

        # En büyük 3 kategori satırı.
        y = 316
        for row in comparison["weight_rows"][:TOP_CATEGORIES]:
            star = "" if row["own_series"] else "*"
            line = (
                f"{row['category']}: %{row['share_pct']} pay · "
                f"enflasyonu %{row['relative_pct']}{star}"
            )
            parts.append(
                f'  <text x="40" y="{y}" fill="#bdc1c6" '
                f'font-family="system-ui, sans-serif" font-size="16">'
                f"{escape(line)}</text>\n"
            )
            y += 26

    parts.append(
        f'  <text x="40" y="{HEIGHT - 24}" fill="#5f6368" '
        f'font-family="system-ui, sans-serif" font-size="14">'
        f"enflasyonum v{escape(version)}</text>\n"
    )
    parts.append("</svg>\n")
    return "".join(parts)
