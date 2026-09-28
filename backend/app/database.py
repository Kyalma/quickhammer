"""SQLAlchemy engine, session factory, and FastAPI dependency."""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    get_settings().database_url,
    connect_args={"check_same_thread": False},  # SQLite + FastAPI threads
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


# Columns added after the first release. create_all() only creates missing
# TABLES, so existing production databases need an ALTER for new columns.
# Append new entries here instead of ever wiping a live database.
_MIGRATION_COLUMNS = [
    ("players", "is_admin", "BOOLEAN NOT NULL DEFAULT 0"),
]


def _ensure_columns() -> None:
    with engine.begin() as conn:
        for table, column, ddl in _MIGRATION_COLUMNS:
            existing = {
                row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})")
            }
            if existing and column not in existing:
                conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def init_db() -> None:
    """Create all tables and apply additive column migrations. Called on startup."""
    from . import models  # noqa: F401  (register models with Base)

    Base.metadata.create_all(bind=engine)
    _ensure_columns()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
