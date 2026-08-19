"""FastAPI uygulama giriş noktası.

M1.3 kapsamı: /health + tek sayfalık harcama giriş formu.
M1.6 kapsamı: kıyas bloğu — "senin %Y vs resmi %X" tek ekranda.
M2.1 kapsamı: kategori satırlarında ECOICOP alt endeks enflasyonu.
M2.2 kapsamı: /card.svg — paylaşılabilir aylık özet kartı.
M2.3 kapsamı: /history.svg — aylık harcama geçmişi grafiği.
GET /  -> form, kıyas bloğu, son harcamalar, bu ayın toplamı
GET /card.svg -> kıyası tek görselde sunan SVG kart
GET /history.svg -> takvim bazında son 12 ayın aylık toplamları (çubuk grafik)
POST /expenses -> doğrula, kaydet, PRG (303) ile / adresine dön
"""

import logging
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from enflasyonum import __version__, crud
from enflasyonum.card import render_card_svg
from enflasyonum.db import create_session_factory
from enflasyonum.history import (
    monthly_totals,
    render_history_error_svg,
    render_history_svg,
)
from enflasyonum.models import Category, Expense, OfficialCPI
from enflasyonum.personal_index import (
    PersonalIndexError,
    category_relatives_from_db,
    category_weights,
    compute_personal_index,
    headline_relative,
)
from enflasyonum.series import HEADLINE_SERIES

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Enflasyonumdan ne haber?",
    description="Kişisel enflasyon endeksi — kendi sepetinle TÜİK'i kıyasla.",
    version=__version__,
)

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

#: Ekranda yüzdeler 2 ondalıkla gösterilir; hesap 6 ondalıkla yapılır.
TWO_DP = Decimal("0.01")


def get_session():
    """İstek başına DB oturumu.

    Not: Her istekte yeni engine kurmak küçük ölçekte kabul edilebilir;
    testlerin DATABASE_URL'i monkeypatch edebilmesi için bilinçli tercih.
    Yük artarsa app.state üzerinde tek engine'e geçilecek (ROADMAP notu).
    """
    factory = create_session_factory()
    with factory() as session:
        yield session


def _parse_amount(raw: str) -> Decimal:
    """'42,50' veya '42.50' -> Decimal('42.50'). Pozitif olmalı."""
    try:
        value = Decimal(raw.strip().replace(",", "."))
    except InvalidOperation as exc:
        raise ValueError(f"Tutar sayı değil: {raw!r}") from exc
    if value <= 0:
        raise ValueError("Tutar pozitif olmalı")
    return value


def _comparison_context(session: Session) -> dict:
    """Kıyas bloğu verisi (M1.6 + M2.1).

    Pencere: elimizdeki son resmi TÜFE dönemi (current) vs 12 ay öncesi
    (base) — yıllık enflasyon. Sepet: harcama içeren son ay
    (``weights_period``); resmi veri ~1 ay geriden geldiği için sepet ayı
    pencereden bilinçli olarak ayrıdır. M2.1: alt endeksi olan kategoriler
    kendi görelisini kullanır; kalanı manşete düşer. Veri eksikse
    ``comparison=None`` + Türkçe ipucu döner; ana sayfa hiçbir koşulda
    500 vermez.
    """
    latest_cpi = session.scalar(
        select(func.max(OfficialCPI.period)).where(
            OfficialCPI.series_code == HEADLINE_SERIES
        )
    )
    latest_expense = session.scalar(select(func.max(Expense.spent_at)))

    if latest_cpi is None:
        return {
            "comparison": None,
            "comparison_hint": "Resmi TÜFE verisi yok — önce ingest çalıştırılmalı.",
        }
    if latest_expense is None:
        return {
            "comparison": None,
            "comparison_hint": "Kıyas için önce en az bir harcama gir.",
        }

    current = latest_cpi
    base = date(current.year - 1, current.month, 1)
    basket = date(latest_expense.year, latest_expense.month, 1)

    try:
        official_pct = ((headline_relative(session, base, current) - 1) * 100).quantize(
            TWO_DP
        )
        category_relatives = category_relatives_from_db(
            session, base, current, category_weights(session, basket)
        )
        result = compute_personal_index(
            session,
            base=base,
            current=current,
            category_relatives=category_relatives,
            weights_period=basket,
        )
    except PersonalIndexError as exc:
        return {"comparison": None, "comparison_hint": f"Kıyas hesaplanamadı: {exc}"}

    personal_pct = result.inflation_pct.quantize(TWO_DP)
    total = sum(result.weights.values())
    weight_rows = [
        {
            "category": cat,
            "amount": amount,
            "share_pct": (amount / total * 100).quantize(TWO_DP),
            "relative_pct": ((result.relatives[cat] - 1) * 100).quantize(TWO_DP),
            "own_series": cat in category_relatives,
        }
        for cat, amount in sorted(
            result.weights.items(), key=lambda kv: kv[1], reverse=True
        )
    ]
    return {
        "comparison": {
            "personal_pct": personal_pct,
            "official_pct": official_pct,
            "diff_pct": (personal_pct - official_pct).quantize(TWO_DP),
            "base_period": base,
            "current_period": current,
            "basket_period": basket,
            "weight_rows": weight_rows,
            "weights_total": total,
        },
        "comparison_hint": None,
    }


def _index_context(session: Session, error: str | None = None) -> dict:
    today = date.today()
    rows = session.execute(
        select(Expense, Category.name)
        .join(Category, Expense.category_id == Category.id)
        .order_by(Expense.spent_at.desc(), Expense.id.desc())
        .limit(20)
    ).all()
    return {
        "expenses": [
            {
                "spent_at": exp.spent_at,
                "category": cat_name,
                "description": exp.description,
                "amount": exp.amount,
            }
            for exp, cat_name in rows
        ],
        "monthly_total": crud.monthly_total(session, today.year, today.month),
        "today": today,
        "error": error,
        "version": __version__,
        **_comparison_context(session),
    }


@app.get("/health")
def health() -> dict[str, str]:
    """Canlılık kontrolü — deploy ve CI smoke testinin dayanak noktası."""
    return {"status": "ok", "version": __version__}


@app.get("/", response_class=HTMLResponse)
def index(request: Request, session: Session = Depends(get_session)):
    return templates.TemplateResponse(request, "index.html", _index_context(session))


@app.get("/card.svg")
def card(session: Session = Depends(get_session)) -> Response:
    """Paylaşılabilir aylık özet kartı (M2.2).

    Ana sayfayla aynı kıyas verisini SVG olarak sunar; veri eksikse
    ipucu kartı döner — asla 500 vermez. Cache kapalı: kart her istekte
    güncel veriden üretilir.
    """
    ctx = _comparison_context(session)
    svg = render_card_svg(ctx["comparison"], ctx["comparison_hint"], __version__)
    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={"Cache-Control": "no-store"},
    )


@app.get("/history.svg")
def history(session: Session = Depends(get_session)) -> Response:
    """Aylık harcama geçmişi grafiği (M2.3).

    Tüm harcamaları çekip Python tarafında takvim ayı bazında toplar
    (gerekçe: history.py modül docstring'i). Veri yokken Türkçe ipucu,
    beklenmeyen hatada (örn. DB erişilemez) hata kartı döner — asla
    500 vermez. Cache kapalı: grafik her istekte güncel veriden üretilir.
    """
    try:
        rows = session.execute(select(Expense.spent_at, Expense.amount)).all()
        svg = render_history_svg(monthly_totals(rows), __version__)
    except Exception:
        logger.exception("history.svg üretilemedi; hata kartı dönülüyor")
        svg = render_history_error_svg(__version__)
    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={"Cache-Control": "no-store"},
    )


@app.post("/expenses")
def create_expense(
    request: Request,
    session: Session = Depends(get_session),
    description: str = Form(...),
    amount: str = Form(...),
    category: str = Form(...),
    spent_at: date = Form(...),
):
    description = description.strip()
    category = category.strip().lower()
    error: str | None = None
    if not description:
        error = "Açıklama boş olamaz."
    elif not category:
        error = "Kategori boş olamaz."
    else:
        try:
            value = _parse_amount(amount)
        except ValueError as exc:
            error = str(exc)

    if error is not None:
        return templates.TemplateResponse(
            request,
            "index.html",
            _index_context(session, error=error),
            status_code=422,
        )

    crud.add_expense(
        session,
        category_name=category,
        description=description,
        amount=value,
        spent_at=spent_at,
    )
    # PRG: POST sonrası 303 -> tarayıcıda F5 çift kayıt üretmez.
    return RedirectResponse(url="/", status_code=303)
