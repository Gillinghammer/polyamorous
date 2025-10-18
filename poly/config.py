"""Configuration helpers for Poly."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import yaml


DEFAULT_CONFIG_PATH = Path.home() / ".poly" / "config.yml"
DEFAULT_DB_PATH = Path.home() / ".poly" / "trades.db"


@dataclass(slots=True)
class ResearchConfig:
    min_confidence_threshold: float = 70.0
    min_edge_threshold: float = 0.10


@dataclass(slots=True)
class PaperTradingConfig:
    default_stake: float = 100.0


@dataclass(slots=True)
class PollConfig:
    top_n: int = 20
    exclude_categories: tuple[str, ...] = ("sports", "esports")
    liquidity_weight_open_interest: float = 0.7
    liquidity_weight_volume_24h: float = 0.3


@dataclass(slots=True)
class AppConfig:
    research: ResearchConfig = ResearchConfig()
    paper_trading: PaperTradingConfig = PaperTradingConfig()
    polls: PollConfig = PollConfig()
    database_path: Path = DEFAULT_DB_PATH


def load_config(path: Path | None = None) -> AppConfig:
    """Load application configuration from YAML or fall back to defaults."""

    config_path = path or DEFAULT_CONFIG_PATH
    if not config_path.exists():
        return AppConfig()

    with config_path.open("r", encoding="utf-8") as handle:
        raw: Dict[str, Any] = yaml.safe_load(handle) or {}

    research = raw.get("research", {})
    paper_trading = raw.get("paper_trading", {})
    polls = raw.get("polls", {})
    database = raw.get("database", {})

    return AppConfig(
        research=ResearchConfig(
            min_confidence_threshold=float(research.get("min_confidence_threshold", 70.0)),
            min_edge_threshold=float(research.get("min_edge_threshold", 0.10)),
        ),
        paper_trading=PaperTradingConfig(
            default_stake=float(paper_trading.get("default_stake", 100.0))
        ),
        polls=PollConfig(
            top_n=int(polls.get("top_n", 20)),
            exclude_categories=tuple(
                str(category) for category in polls.get("exclude_categories", ["sports", "esports"])
            ),
            liquidity_weight_open_interest=float(
                polls.get("liquidity_weight", {}).get("open_interest", 0.7)
            ),
            liquidity_weight_volume_24h=float(
                polls.get("liquidity_weight", {}).get("volume_24h", 0.3)
            ),
        ),
        database_path=Path(database.get("path", DEFAULT_DB_PATH)),
    )
