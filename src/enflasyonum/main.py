"""FastAPI uygulama giriş noktası.

M1.3 kapsamı: /health + tek sayfalık harcama giriş formu.
GET /  -> form, son harcamalar, bu ayın toplamı
POST /expenses -> doğrula, kaydet, PRG (303) ile / adresine dön
"""

from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from enflasyonum import __version__, crud
from enflasyonum.db import create_session_factory
from enflasyonum.models import Category, Expense

app = FastAPI(
    title="Enflasyonumdan ne haber?",
    description="Kişisel enflasyon endeksi — kendi sepetinle TÜİK'i kıyasla.",
    version=__version__,
)

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


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
    }


@app.get("/health")
def health() -> dict[str, str]:
    """Canlılık kontrolü — deploy ve CI smoke testinin dayanak noktası."""
    return {"status": "ok", "version": __version__}


@app.get("/", response_class=HTMLResponse)
def index(request: Request, session: Session = Depends(get_session)):
    return templates.TemplateResponse(request, "index.html", _index_context(session))


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
