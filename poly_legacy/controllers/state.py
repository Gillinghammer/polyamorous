from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..models import ResearchProgress, ResearchResult


@dataclass
class AppState:
    research_running: Dict[str, bool] = field(default_factory=dict)
    progress_by_market: Dict[str, ResearchProgress] = field(default_factory=dict)
    research_results_by_market: Dict[str, ResearchResult] = field(default_factory=dict)
    evaluations_by_market: Dict[str, object] = field(default_factory=dict)
    logs_by_market: Dict[str, List[str]] = field(default_factory=dict)
    progress_pct_by_market: Dict[str, int] = field(default_factory=dict)
    history_row_index_by_id: Dict[str, int] = field(default_factory=dict)
    question_by_market_id: Dict[str, str] = field(default_factory=dict)

    current_page: int = 1
    page_size: int = 50
    day_filter: Optional[int] = None
    category_filter: Optional[str] = None
    sort_key: str = "liquidity"
    filter_researched: bool = False
    research_history_filter: str = "all"

    selected_trade_id: Optional[int] = None
    entry_stake_by_market: Dict[str, float] = field(default_factory=dict)
    active_market_id: Optional[str] = None


