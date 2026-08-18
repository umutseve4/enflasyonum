"""index_value hassasiyetini genişlet: Numeric(12,4) -> Numeric(14,6)

2025=100 TÜFE serisi 6 ondalık basamak taşıyor (ör. 88.578291).
Numeric(12,4) Postgres'te değeri sessizce 4 haneye yuvarlıyordu.

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-18
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("official_cpi") as batch:
        batch.alter_column(
            "index_value",
            existing_type=sa.Numeric(12, 4),
            type_=sa.Numeric(14, 6),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("official_cpi") as batch:
        batch.alter_column(
            "index_value",
            existing_type=sa.Numeric(14, 6),
            type_=sa.Numeric(12, 4),
            existing_nullable=False,
        )
