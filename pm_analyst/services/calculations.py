from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class MarketSnapshot:
    market_id: str
    price_yes: float
    price_no: float
    resolves_at: datetime


@dataclass
class EdgeReport:
    edge: float
    apr: float
    roi: float
    days_to_expiry: float
    side: str


def implied_probability(price: float) -> float:
    return price


def compute_roi(model_prob: float, price: float) -> float:
    if price <= 0:
        return 0.0
    return (model_prob - price) / price


def annualized_apr(roi: float, days_to_expiry: float) -> float:
    if days_to_expiry <= 0:
        return 0.0
    return roi * (365.0 / days_to_expiry)


def select_side(model_prob: float, prices: dict[str, float]) -> tuple[str, float]:
    yes_roi = compute_roi(model_prob, prices["yes"])
    no_model_prob = 1 - model_prob
    no_roi = compute_roi(no_model_prob, prices["no"])
    if yes_roi >= no_roi:
        return "yes", yes_roi
    return "no", no_roi


def evaluate_market(model_prob: float, prices: dict[str, float], resolves_at: datetime) -> EdgeReport:
    side, roi = select_side(model_prob, prices)
    price = prices[side]
    edge = model_prob - prices["yes"] if side == "yes" else (1 - model_prob) - prices["no"]
    days_to_expiry = max((resolves_at - datetime.utcnow()).total_seconds() / 86400, 0.01)
    apr = annualized_apr(roi, days_to_expiry)
    return EdgeReport(edge=edge, apr=apr, roi=roi, days_to_expiry=days_to_expiry, side=side)


def recommend_stake(policy: str, bankroll: float, risk_budget: float, confidence: float, roi: float, max_fraction: float = 0.05) -> float:
    if policy == "kelly":
        kelly_fraction = max(min(roi / (1 if roi != 0 else 1), max_fraction), -max_fraction)
        fraction = min(abs(kelly_fraction) * confidence, max_fraction)
    else:
        fraction = risk_budget * confidence
    return bankroll * max(fraction, 0)


__all__ = [
    "MarketSnapshot",
    "EdgeReport",
    "evaluate_market",
    "recommend_stake",
]
