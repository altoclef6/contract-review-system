from __future__ import annotations

from collections.abc import Generator
from functools import lru_cache
from pathlib import Path

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from contract_review.core.config import get_settings
from contract_review.database import models  # noqa: F401
from contract_review.database.base import Base


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    connect_args = (
        {"check_same_thread": False}
        if settings.database_url.get_secret_value().startswith("sqlite")
        else {}
    )
    return create_engine(
        settings.database_url.get_secret_value(),
        pool_pre_ping=True,
        pool_recycle=1800,
        connect_args=connect_args,
    )


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    with get_session_factory()() as session:
        yield session


def init_database() -> None:
    settings = get_settings()
    if not settings.database_enabled:
        return
    engine = get_engine()
    if engine.dialect.name == "sqlite":
        database_path = Path(engine.url.database or "")
        database_path.parent.mkdir(parents=True, exist_ok=True)
        Base.metadata.create_all(engine)
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
