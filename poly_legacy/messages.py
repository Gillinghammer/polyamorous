from __future__ import annotations

from textual.message import Message

from .models import ResearchProgress, ResearchResult


class ResearchProgressMsg(Message):
    def __init__(self, market_id: str, progress: ResearchProgress) -> None:
        self.market_id = market_id
        self.progress = progress
        super().__init__()


class ResearchCompleteMsg(Message):
    def __init__(self, market_id: str, result: ResearchResult, evaluation) -> None:
        self.market_id = market_id
        self.result = result
        self.evaluation = evaluation
        super().__init__()


class ResearchFailedMsg(Message):
    def __init__(self, market_id: str, error: str) -> None:
        self.market_id = market_id
        self.error = error
        super().__init__()


class PollSelectedMsg(Message):
    def __init__(self, market_id: str) -> None:
        self.market_id = market_id
        super().__init__()


class TradeSelectedMsg(Message):
    def __init__(self, trade_id: int) -> None:
        self.trade_id = trade_id
        super().__init__()


