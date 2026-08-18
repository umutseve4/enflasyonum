"""initial schema: categories, expenses, official_cpi

Revision ID: 0001
Revises:
Create Date: 2026-08-18
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
    )
    op.create_table(
        "expenses",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "category_id", sa.Integer, sa.ForeignKey("categories.id"), nullable=False
        ),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("spent_at", sa.Date, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_expenses_spent_at", "expenses", ["spent_at"])
    op.create_table(
        "official_cpi",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("period", sa.Date, nullable=False, unique=True),
        sa.Column("index_value", sa.Numeric(12, 4), nullable=False),
        sa.Column("source", sa.String(50), nullable=False, server_default="TUIK"),
    )


def downgrade() -> None:
    op.drop_table("official_cpi")
    op.drop_index("ix_expenses_spent_at", table_name="expenses")
    op.drop_table("expenses")
    op.drop_table("categories")
