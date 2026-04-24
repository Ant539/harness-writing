"""Database engine, session dependency, and initialization."""

from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

from app.config import settings
from app import models  # noqa: F401


def _connect_args(database_url: str) -> dict[str, bool]:
    if database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


engine = create_engine(settings.database_url, connect_args=_connect_args(settings.database_url))


def create_db_and_tables() -> None:
    """Create all tables for the local prototype."""
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a SQLModel session."""
    with Session(engine) as session:
        yield session
