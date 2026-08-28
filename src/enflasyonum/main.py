"""FastAPI application for Enflasyonum."""

from __future__ import annotations

import csv
import io
import math
import os
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from fastapi import Depends, FastAPI, Form, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from enflasyonum import __version__
from enflasyonum.calculator import calculate_personal_index, format_result
from enflasyonum.database import get_session, init_db
from enflasyonum.models import CPIIndex, Category, Expense

BASE_DIR = Path(__file__).resolve().parent
app = FastAPI(title="Enflasyonumdan ne haber?", version=__version__)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")

USAGE_TARGET_DAYS = 14


@app.on_event("startup")
def startup() -> None:
    init_db()


def _parse_amount(raw: str) -> Decimal:
    normalized = raw.strip().replace(",", ".")
    try:
        value = Decimal(normalized)
    except InvalidOperation as exc:
        raise ValueError("Tutar sayısal olmalıdır.") from exc
    if value <= 0:
        raise ValueError("Tutar sıfırdan büyük olmalıdır.")
    return value.quantize(Decimal("0.01"))


def _month_bounds(month: str | None) -> tuple[date | None, date | None]:
    if not month:
        return None, None
    try:
        start = datetime.strptime(month, "%Y-%m").date().replace(day=1)
    except ValueError:
        return None, None
    if start.month == 12:
        end = date(start.year + 1, 1, 1)
    else:
        end = date(start.year, start.month + 1, 1)
    return start, end


def _index_context(session: Session, error: str | None = None) -> dict:
    rows = session.execute(
        select(Expense, Category.name)
        .join(Category, Expense.category_id == Category.id)
        .order_by(Expense.spent_at.desc(), Expense.id.desc())
        .limit(20)
    ).all()
    categories = session.scalars(select(Category).order_by(Category.name)).all()
    result = calculate_personal_index(session)
    comparison = None
    if result:
        comparison = format_result(result)
    return {
        "expenses": rows,
        "categories": categories,
        "comparison": comparison,
        "error": error,
        "version": __version__,
        "today": date.today().isoformat(),
    }


@app.get("/", response_class=HTMLResponse)
def index(request: Request, session: Session = Depends(get_session)):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context=_index_context(session),
    )


@app.post("/expenses")
def create_expense(
    request: Request,
    amount: str = Form(...),
    category: str = Form(...),
    spent_at: date = Form(...),
    description: str = Form(""),
    session: Session = Depends(get_session),
):
    try:
        parsed_amount = _parse_amount(amount)
    except ValueError as exc:
        context = _index_context(session, str(exc))
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context=context,
            status_code=422,
        )

    category_name = category.strip()
    if not category_name:
        context = _index_context(session, "Kategori boş bırakılamaz.")
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context=context,
            status_code=422,
        )

    category_row = session.scalar(
        select(Category).where(func.lower(Category.name) == category_name.lower())
    )
    if category_row is None:
        category_row = Category(name=category_name)
        session.add(category_row)
        session.flush()

    session.add(
        Expense(
            amount=parsed_amount,
            category_id=category_row.id,
            spent_at=spent_at,
            description=description.strip() or None,
        )
    )
    session.commit()
    return RedirectResponse(url="/", status_code=303)


@app.get("/usage-progress")
def usage_progress(session: Session = Depends(get_session)) -> dict[str, int | bool]:
    """Return only aggregate progress toward M1's 14 distinct usage-day gate."""
    distinct_days = session.scalar(
        select(func.count(func.distinct(Expense.spent_at)))
    ) or 0
    distinct_days = int(distinct_days)
    remaining_days = max(USAGE_TARGET_DAYS - distinct_days, 0)
    return {
        "distinct_days": distinct_days,
        "target_days": USAGE_TARGET_DAYS,
        "remaining_days": remaining_days,
        "complete": distinct_days >= USAGE_TARGET_DAYS,
    }


@app.get("/export.csv")
def export_csv(
    month: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}$"),
    session: Session = Depends(get_session),
):
    start, end = _month_bounds(month)
    query = (
        select(Expense, Category.name)
        .join(Category, Expense.category_id == Category.id)
        .order_by(Expense.spent_at, Expense.id)
    )
    if start and end:
        query = query.where(Expense.spent_at >= start, Expense.spent_at < end)
    rows = session.execute(query).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["tarih", "kategori", "tutar", "aciklama"])
    for expense, category_name in rows:
        writer.writerow(
            [
                expense.spent_at.isoformat(),
                category_name,
                f"{expense.amount:.2f}",
                expense.description or "",
            ]
        )
    filename = "enflasyonum.csv" if not month else f"enflasyonum-{month}.csv"
    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _empty_svg(message: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="720" height="240" role="img" aria-label="{message}">
<rect width="100%" height="100%" fill="#fffaf2"/><text x="50%" y="50%" text-anchor="middle" fill="#4a3f35" font-family="sans-serif" font-size="22">{message}</text></svg>"""


def _line_points(values: list[float], width: int, height: int, pad: int) -> str:
    if not values:
        return ""
    low, high = min(values), max(values)
    span = high - low or 1.0
    x_span = width - 2 * pad
    y_span = height - 2 * pad
    points = []
    for index, value in enumerate(values):
        x = pad if len(values) == 1 else pad + index * x_span / (len(values) - 1)
        y = pad + (high - value) * y_span / span
        points.append(f"{x:.1f},{y:.1f}")
    return " ".join(points)


@app.get("/history.svg")
def history_svg(session: Session = Depends(get_session)):
    expenses = session.scalars(select(Expense).order_by(Expense.spent_at)).all()
    cpi_rows = session.scalars(select(CPIIndex).order_by(CPIIndex.period)).all()
    if not expenses or not cpi_rows:
        return Response(_empty_svg("Grafik için yeterli veri yok"), media_type="image/svg+xml")

    monthly: dict[str, Decimal] = {}
    for expense in expenses:
        key = expense.spent_at.strftime("%Y-%m")
        monthly[key] = monthly.get(key, Decimal("0")) + expense.amount
    cpi_map = {row.period: float(row.value) for row in cpi_rows}
    labels = sorted(set(monthly).intersection(cpi_map))
    if len(labels) < 2:
        return Response(_empty_svg("Grafik için en az iki ortak ay gerekli"), media_type="image/svg+xml")

    base_spend = float(monthly[labels[0]]) or 1.0
    base_cpi = cpi_map[labels[0]] or 1.0
    personal = [float(monthly[label]) / base_spend * 100 for label in labels]
    official = [cpi_map[label] / base_cpi * 100 for label in labels]
    width, height, pad = 720, 300, 50
    all_values = personal + official
    low, high = min(all_values), max(all_values)
    if math.isclose(low, high):
        high = low + 1
    personal_points = _line_points(personal, width, height, pad)
    official_points = _line_points(official, width, height, pad)
    first_label, last_label = labels[0], labels[-1]
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" role="img" aria-label="Kişisel enflasyon ve TÜFE geçmişi">
<rect width="100%" height="100%" fill="#fffaf2"/><line x1="{pad}" y1="{height-pad}" x2="{width-pad}" y2="{height-pad}" stroke="#cabca8"/>
<polyline points="{personal_points}" fill="none" stroke="#d95d39" stroke-width="4"/><polyline points="{official_points}" fill="none" stroke="#33658a" stroke-width="4"/>
<text x="{pad}" y="25" fill="#d95d39" font-family="sans-serif" font-size="16">Kişisel</text><text x="140" y="25" fill="#33658a" font-family="sans-serif" font-size="16">TÜFE</text>
<text x="{pad}" y="{height-12}" fill="#4a3f35" font-family="sans-serif" font-size="13">{first_label}</text><text x="{width-pad}" y="{height-12}" text-anchor="end" fill="#4a3f35" font-family="sans-serif" font-size="13">{last_label}</text>
<text x="{width-pad}" y="45" text-anchor="end" fill="#4a3f35" font-family="sans-serif" font-size="13">Endeks aralığı: {low:.1f}–{high:.1f}</text></svg>"""
    return Response(svg, media_type="image/svg+xml")


@app.get("/card.svg")
def card_svg(session: Session = Depends(get_session)):
    result = calculate_personal_index(session)
    if not result:
        return Response(_empty_svg("Henüz hesaplanabilir sonuç yok"), media_type="image/svg+xml")
    formatted = format_result(result)
    personal = formatted["personal_change"]
    official = formatted["official_change"]
    difference = formatted["difference"]
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="720" height="360" role="img" aria-label="Enflasyonum sonuç kartı">
<defs><linearGradient id="bg" x1="0" x2="1"><stop offset="0" stop-color="#fff3df"/><stop offset="1" stop-color="#f7d6bd"/></linearGradient></defs>
<rect width="100%" height="100%" rx="28" fill="url(#bg)"/><text x="48" y="65" fill="#4a2f25" font-family="sans-serif" font-size="30" font-weight="700">Enflasyonumdan ne haber?</text>
<text x="48" y="120" fill="#6a4b3c" font-family="sans-serif" font-size="18">{formatted['start_period']} → {formatted['end_period']}</text>
<text x="48" y="188" fill="#d95d39" font-family="sans-serif" font-size="25" font-weight="700">Kişisel: %{personal}</text><text x="48" y="235" fill="#33658a" font-family="sans-serif" font-size="25" font-weight="700">TÜFE: %{official}</text>
<text x="48" y="292" fill="#4a2f25" font-family="sans-serif" font-size="22">Fark: {difference} yüzde puan</text><text x="672" y="330" text-anchor="end" fill="#8c6b58" font-family="sans-serif" font-size="14">v{__version__}</text></svg>"""
    return Response(svg, media_type="image/svg+xml")


@app.get("/health")
def health() -> JSONResponse:
    return JSONResponse({"status": "ok", "version": __version__, "database": os.getenv("DATABASE_URL", "sqlite")[:12]})
