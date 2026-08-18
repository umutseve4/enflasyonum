"""Database engine/session helpers.

DATABASE_URL ortam değişkeni yoksa yerel geliştirme için SQLite'a düşer.
Üretim ve CI her zaman PostgreSQL kullanır (postgresql+psycopg://...).
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

DEFAULT_URL = "sqlite:///./enflasyonum.db"


def get_database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_URL)


def create_session_factory(url: str | None = None) -> sessionmaker[Session]:
    engine = create_engine(url or get_database_url())
    return sessionmaker(bind=engine)
