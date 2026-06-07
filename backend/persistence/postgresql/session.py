from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.persistence.postgresql.config import database_url


@lru_cache(maxsize=8)
def create_postgresql_engine(url: str | None = None):
    return create_engine(url or database_url(), pool_pre_ping=True)


@lru_cache(maxsize=8)
def session_factory(url: str | None = None) -> sessionmaker[Session]:
    return sessionmaker(bind=create_postgresql_engine(url), expire_on_commit=False)


@contextmanager
def session_scope(url: str | None = None) -> Iterator[Session]:
    factory = session_factory(url)
    with factory() as session:
        with session.begin():
            yield session
