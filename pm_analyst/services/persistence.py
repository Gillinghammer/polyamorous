from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlmodel import Session, SQLModel, create_engine

DEFAULT_DB_PATH = Path.home() / ".pm_analyst" / "state.db"


def get_engine(db_path: Path | None = None):
    path = db_path or DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{path}", echo=False)


def init_db(engine=None) -> None:
    engine = engine or get_engine()
    SQLModel.metadata.create_all(engine)


@contextmanager
def session_scope(engine=None) -> Iterator[Session]:
    engine = engine or get_engine()
    with Session(engine) as session:
        yield session


__all__ = ["get_engine", "init_db", "session_scope", "DEFAULT_DB_PATH"]
