"""official_cpi çoklu seri desteği: series_code sütunu + (seri, dönem) tekliği

M2.1: manşet TÜFE'nin yanına 13 ECOICOP bölüm endeksi geliyor; aynı dönem
artık seri başına bir satır taşır. unique(period) kısıtı
unique(series_code, period) ile değiştirilir. Mevcut satırlar server_default
ile manşet seriye (TP.TUKFIY2025.GENEL) backfill edilir — veri kaybı yok.

SQLite'ta 0001'in isimsiz inline UNIQUE(period) kısıtı drop_constraint ile
düşürülemez; batch modda ``copy_from`` ile tablo, kısıt OLMADAN yeniden
kurulur (Alembic'in belgelenmiş yöntemi). PostgreSQL'de kısıtın otomatik adı
``official_cpi_period_key``dir ve doğrudan düşürülür.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-19
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

HEADLINE = "TP.TUKFIY2025.GENEL"
UQ_NAME = "uq_official_cpi_series_period"


def _current_table() -> sa.Table:
    """SQLite batch ``copy_from`` tanımı: kısıtsız güncel tablo şeması.

    ``copy_from`` verildiğinde Alembic tabloyu yansıtmak yerine bu tanımı
    kullanır; tanımda unique(period) OLMADIĞI için yeniden kurulan tabloda
    eski kısıt kalkar.
    """
    return sa.Table(
        "official_cpi",
        sa.MetaData(),
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("period", sa.Date, nullable=False),
        sa.Column("index_value", sa.Numeric(14, 6), nullable=False),
        sa.Column("source", sa.String(50), nullable=False, server_default="TUIK"),
        sa.Column("series_code", sa.String(40), nullable=False, server_default=HEADLINE),
    )


def upgrade() -> None:
    op.add_column(
        "official_cpi",
        sa.Column("series_code", sa.String(40), nullable=False, server_default=HEADLINE),
    )
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table(
            "official_cpi", copy_from=_current_table(), recreate="always"
        ) as batch:
            batch.create_unique_constraint(UQ_NAME, ["series_code", "period"])
    else:
        op.drop_constraint("official_cpi_period_key", "official_cpi", type_="unique")
        op.create_unique_constraint(UQ_NAME, "official_cpi", ["series_code", "period"])


def downgrade() -> None:
    # Alt endeks satırları eski şemaya sığmaz (unique(period) çakışır) -> silinir.
    op.execute(f"DELETE FROM official_cpi WHERE series_code != '{HEADLINE}'")
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table(
            "official_cpi", copy_from=_current_table(), recreate="always"
        ) as batch:
            batch.drop_column("series_code")
            batch.create_unique_constraint("official_cpi_period_key", ["period"])
    else:
        op.drop_constraint(UQ_NAME, "official_cpi", type_="unique")
        op.drop_column("official_cpi", "series_code")
        op.create_unique_constraint("official_cpi_period_key", "official_cpi", ["period"])
