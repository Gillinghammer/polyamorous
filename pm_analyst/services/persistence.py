from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Iterator, TYPE_CHECKING

from sqlmodel import Session, SQLModel, create_engine

from ..models.db import Market

if TYPE_CHECKING:
    from ..services.polymarket import MarketData

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


def upsert_markets(session: Session, markets: Iterable["MarketData"]) -> None:
    """Persist market snapshots for downstream commands."""

    for market in markets:
        existing = session.get(Market, market.id)
        payload = {
            "slug": market.slug,
            "question": market.question,
            "resolves_at": market.resolves_at,
            "price_yes": market.prices.get("yes", 0.0),
            "price_no": market.prices.get("no", 0.0),
            "open_interest": market.open_interest,
            "volume_24h": market.volume_24h,
            "depth": market.top_of_book_depth,
            "category": market.category,
            "volatility_hint": market.volatility_hint,
        }
        if existing:
            for key, value in payload.items():
                setattr(existing, key, value)
            session.add(existing)
        else:
            session.add(Market(id=market.id, **payload))


__all__ = ["get_engine", "init_db", "session_scope", "upsert_markets", "DEFAULT_DB_PATH"]
