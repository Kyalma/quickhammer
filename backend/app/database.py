"""SQLAlchemy engine, session factory, migrations, and FastAPI dependency."""
import os
from collections.abc import Generator
from pathlib import Path

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


def _alembic_config():
    """Alembic config built in code so it works from any working directory,
    both in the repo (backend/alembic) and in the container (/app/alembic)."""
    from alembic.config import Config

    config = Config()
    config.set_main_option("script_location", str(Path(__file__).resolve().parent.parent / "alembic"))
    config.set_main_option("sqlalchemy.url", get_settings().database_url)
    return config


def run_migrations() -> None:
    """Bring the database to the latest revision, preserving existing data.

    Works on an empty database and on one created before Alembic existed: the
    baseline revision is idempotent, so it fills in whatever is missing instead
    of needing to be stamped. Never uses create_all, because the models drift
    ahead of the baseline and would create future columns too early.
    """
    from alembic import command

    from . import models  # noqa: F401  (register models with Base)

    config = _alembic_config()
    # Share our connection so in-memory and single-file engines both work.
    with engine.begin() as conn:
        config.attributes["connection"] = conn
        command.upgrade(config, "head")


def init_db() -> None:
    """Startup hook. Set QH_SKIP_MIGRATIONS=1 to bypass (tests manage their
    own schema and must not touch the real database)."""
    if os.environ.get("QH_SKIP_MIGRATIONS") == "1":
        return
    run_migrations()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
