"""Temel CRUD işlemleri — M1.2 kapsamı."""

from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from enflasyonum.models import Category, Expense, OfficialCPI


def get_or_create_category(session: Session, name: str) -> Category:
    cat = session.scalar(select(Category).where(Category.name == name))
    if cat is None:
        cat = Category(name=name)
        session.add(cat)
        session.commit()
        session.refresh(cat)
    return cat


def add_expense(
    session: Session,
    *,
    category_name: str,
    description: str,
    amount: Decimal,
    spent_at: date,
) -> Expense:
    cat = get_or_create_category(session, category_name)
    exp = Expense(
        category_id=cat.id, description=description, amount=amount, spent_at=spent_at
    )
    session.add(exp)
    session.commit()
    session.refresh(exp)
    return exp


def list_expenses(
    session: Session,
    *,
    start: date | None = None,
    end: date | None = None,
) -> list[Expense]:
    stmt = select(Expense).order_by(Expense.spent_at, Expense.id)
    if start is not None:
        stmt = stmt.where(Expense.spent_at >= start)
    if end is not None:
        stmt = stmt.where(Expense.spent_at <= end)
    return list(session.scalars(stmt))


def monthly_total(session: Session, year: int, month: int) -> Decimal:
    start = date(year, month, 1)
    end = date(year, month, calendar.monthrange(year, month)[1])
    total = session.scalar(
        select(func.sum(Expense.amount)).where(Expense.spent_at.between(start, end))
    )
    if total is None:
        return Decimal("0")
    return Decimal(str(total))


def upsert_official_cpi(
    session: Session,
    *,
    period: date,
    index_value: Decimal,
    source: str = "TUIK",
) -> OfficialCPI:
    row = session.scalar(select(OfficialCPI).where(OfficialCPI.period == period))
    if row is None:
        row = OfficialCPI(period=period, index_value=index_value, source=source)
        session.add(row)
    else:
        row.index_value = index_value
        row.source = source
    session.commit()
    session.refresh(row)
    return row


def list_official_cpi(session: Session) -> list[OfficialCPI]:
    return list(session.scalars(select(OfficialCPI).order_by(OfficialCPI.period)))
