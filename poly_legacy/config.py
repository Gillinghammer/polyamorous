"""Configuration helpers for Poly."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict

import yaml


DEFAULT_CONFIG_PATH = Path.home() / ".poly" / "config.yml"
DEFAULT_DB_PATH = Path.home() / ".poly" / "trades.db"


@dataclass(slots=True)
class ResearchConfig:
    min_confidence_threshold: float = 70.0
    min_edge_threshold: float = 0.10
    # Deep research controls
    model_name: str = "grok-4-fast"
    default_rounds: int = 20
    enable_code_execution: bool = False
    # Topic planning
    topic_count_min: int = 10
    topic_count_max: int = 20
    # Token pricing (USD per 1K tokens). Used for cost estimates only.
    prompt_token_price_per_1k: float = 0.0
    completion_token_price_per_1k: float = 0.0
    reasoning_token_price_per_1k: float = 0.0
    # Media understanding toggles
    enable_image_understanding: bool = True
    enable_video_understanding: bool = True


@dataclass(slots=True)
class PaperTradingConfig:
    default_stake: float = 100.0
    price_refresh_seconds: int = 60
    starting_cash: float = 10_000.0
    max_risk_per_trade_pct: float = 0.02


@dataclass(slots=True)
class PollConfig:
    top_n: int = 20
    exclude_categories: tuple[str, ...] = ("sports", "esports")
    liquidity_weight_open_interest: float = 0.7
    liquidity_weight_volume_24h: float = 0.3


@dataclass(slots=True)
class AppConfig:
    research: ResearchConfig = field(default_factory=ResearchConfig)
    paper_trading: PaperTradingConfig = field(default_factory=PaperTradingConfig)
    polls: PollConfig = field(default_factory=PollConfig)
    database_path: Path = field(default_factory=lambda: DEFAULT_DB_PATH)


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
            model_name=str(research.get("model_name", "grok-4-fast")),
            default_rounds=int(research.get("default_rounds", 20)),
            enable_code_execution=bool(research.get("enable_code_execution", False)),
            topic_count_min=int(research.get("topic_count_min", 10)),
            topic_count_max=int(research.get("topic_count_max", 20)),
            prompt_token_price_per_1k=float(research.get("prompt_token_price_per_1k", 0.0)),
            completion_token_price_per_1k=float(research.get("completion_token_price_per_1k", 0.0)),
            reasoning_token_price_per_1k=float(research.get("reasoning_token_price_per_1k", 0.0)),
            enable_image_understanding=bool(research.get("enable_image_understanding", True)),
            enable_video_understanding=bool(research.get("enable_video_understanding", True)),
        ),
        paper_trading=PaperTradingConfig(
            default_stake=float(paper_trading.get("default_stake", 100.0)),
            price_refresh_seconds=int(paper_trading.get("price_refresh_seconds", 60)),
            starting_cash=float(paper_trading.get("starting_cash", 10_000.0)),
            max_risk_per_trade_pct=float(paper_trading.get("max_risk_per_trade_pct", 0.02)),
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
