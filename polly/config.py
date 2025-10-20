from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class Config:
    """Application configuration loaded from env and config file.

    Follows No-Fallback: required keys must be present for features that need them.
    """

    db_path: Path
    api_base: str
    xai_api_key: Optional[str]
    polymarket_api_key: Optional[str]
    
    # Agent settings
    agent_enabled: bool = False
    agent_window_days: int = 7

    @staticmethod
    def load() -> "Config":
        # Load .env if present to populate environment variables
        try:
            from dotenv import load_dotenv  # type: ignore

            load_dotenv()
        except Exception:
            # dotenv is optional; absence should not crash app
            pass

        home = Path.home()
        config_dir = home / ".config" / "polly"
        config_dir.mkdir(parents=True, exist_ok=True)

        # DB path
        db_path = Path(os.getenv("POLLY_DB_PATH", str(config_dir / "polly.db")))

        # API endpoints
        # Default to CLOB host for py-clob-client markets
        api_base = os.getenv("POLLY_API_BASE", "https://clob.polymarket.com")

        # Secrets (required for research when used)
        xai_api_key = os.getenv("XAI_API_KEY")
        polymarket_api_key = os.getenv("POLYMARKET_API_KEY")

        return Config(
            db_path=db_path,
            api_base=api_base,
            xai_api_key=xai_api_key,
            polymarket_api_key=polymarket_api_key,
            agent_enabled=False,
            agent_window_days=7,
        )


