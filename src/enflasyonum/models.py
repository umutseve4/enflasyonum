"""SQLAlchemy 2.0 ORM modelleri: categories, expenses, official_cpi."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)

    expenses: Mapped[list[Expense]] = relationship(back_populates="category")


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    description: Mapped[str] = mapped_column(String(255))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    spent_at: Mapped[date] = mapped_column(Date, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    category: Mapped[Category] = relationship(back_populates="expenses")


class OfficialCPI(Base):
    __tablename__ = "official_cpi"

    id: Mapped[int] = mapped_column(primary_key=True)
    period: Mapped[date] = mapped_column(Date, unique=True)
    # 2025=100 TÜFE serisi 6 ondalık taşır (ör. 88.578291) — bkz. migration 0002.
    index_value: Mapped[Decimal] = mapped_column(Numeric(14, 6))
    source: Mapped[str] = mapped_column(String(50), default="TUIK", server_default="TUIK")
