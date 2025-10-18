from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict

import yaml

CONFIG_PATH = Path.home() / ".pm_analyst" / "config.yml"


@dataclass
class LiquidityConfig:
    min_oi: float = 200_000.0
    min_vol24h: float = 50_000.0
    min_depth: float = 10_000.0


@dataclass
class ResearchConfig:
    max_rounds: int = 4
    min_confidence: float = 0.6
    min_edge: float = 0.03


@dataclass
class SizingConfig:
    policy: str = "flat"
    bankroll: float = 50_000.0
    risk_budget: float = 0.02
    max_fraction: float = 0.05


@dataclass
class UpdatesConfig:
    quotes_interval_seconds: int = 30


@dataclass
class Settings:
    xai_api_key_env: str = "XAI_API_KEY"
    risk_free_apr: float = 0.048
    risk_free_provider: str = "treasury"
    liquidity: LiquidityConfig = field(default_factory=LiquidityConfig)
    research: ResearchConfig = field(default_factory=ResearchConfig)
    sizing: SizingConfig = field(default_factory=SizingConfig)
    updates: UpdatesConfig = field(default_factory=UpdatesConfig)

    @property
    def xai_api_key(self) -> str | None:
        return os.getenv(self.xai_api_key_env)


def _merge_dict(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge_dict(result[key], value)
        else:
            result[key] = value
    return result


def load_settings(config_path: Path | None = None) -> Settings:
    path = config_path or CONFIG_PATH
    defaults = Settings()
    if not path.exists():
        return defaults

    with path.open("r", encoding="utf-8") as fh:
        loaded = yaml.safe_load(fh) or {}

    merged = _merge_dict(asdict(defaults), loaded)

    liquidity = LiquidityConfig(**merged.get("liquidity", {}))
    research = ResearchConfig(**merged.get("research", {}))
    sizing = SizingConfig(**merged.get("sizing", {}))
    updates = UpdatesConfig(**merged.get("updates", {}))

    return Settings(
        xai_api_key_env=merged.get("xai_api_key_env", defaults.xai_api_key_env),
        risk_free_apr=float(merged.get("risk_free_apr", defaults.risk_free_apr)),
        risk_free_provider=merged.get("risk_free_provider", defaults.risk_free_provider),
        liquidity=liquidity,
        research=research,
        sizing=sizing,
        updates=updates,
    )


__all__ = ["Settings", "load_settings", "CONFIG_PATH"]
