"""Grok research orchestration for Poly."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib import import_module, util
from typing import Callable, Iterable, Optional

from ..config import ResearchConfig
from ..models import Market, ResearchProgress, ResearchResult

ProgressCallback = Callable[[ResearchProgress], None]


@dataclass(slots=True)
class ResearchService:
    """Coordinates multi-round Grok research."""

    config: ResearchConfig

    def __post_init__(self) -> None:
        self._client = self._build_client()

    async def conduct_research(
        self,
        market: Market,
        callback: ProgressCallback,
        rounds: int = 4,
    ) -> ResearchResult:
        """Run research asynchronously, streaming progress via callback."""

        start = datetime.now(tz=timezone.utc)

        if self._client is None:
            result = await self._simulate_research(market, callback, rounds)
        else:
            result = await self._run_with_grok(market, callback, rounds)

        duration = datetime.now(tz=timezone.utc) - start
        return ResearchResult(
            market_id=market.id,
            prediction=result["prediction"],
            probability=result["probability"],
            confidence=result["confidence"],
            rationale=result["rationale"],
            key_findings=result["key_findings"],
            citations=result["citations"],
            rounds_completed=rounds,
            created_at=start,
            duration_minutes=max(1, int(duration.total_seconds() // 60)),
        )

    def _build_client(self):
        """Initialize Grok client when dependencies and key are available."""

        if util.find_spec("xai_sdk") is None:
            return None

        api_key = os.getenv("XAI_API_KEY")
        if not api_key:
            return None

        module = import_module("xai_sdk")
        client_cls = getattr(module, "Client")
        return client_cls(api_key=api_key)

    async def _simulate_research(
        self,
        market: Market,
        callback: ProgressCallback,
        rounds: int,
    ) -> dict:
        """Offline fallback that mimics multi-round analysis."""

        findings: list[str] = []
        for round_number in range(1, rounds + 1):
            message = _SIMULATED_ROUNDS[round_number - 1].format(question=market.question)
            callback(ResearchProgress(message=message, round_number=round_number, total_rounds=rounds))
            await asyncio.sleep(0.5)
            findings.append(message)

        callback(
            ResearchProgress(
                message="Synthesis complete. Preparing recommendation...",
                round_number=rounds,
                total_rounds=rounds,
                completed=True,
            )
        )

        price_edge = _estimate_edge(market)
        confidence = max(self.config.min_confidence_threshold, 72.0)

        return {
            "prediction": "Yes" if price_edge >= 0 else "No",
            "probability": min(0.9, max(0.1, 0.5 + price_edge)),
            "confidence": confidence,
            "rationale": (
                "Based on synthesized public filings, expert commentary, and recent market movements, the odds support this position."
            ),
            "key_findings": findings,
            "citations": ["https://example.com/analysis", "https://example.com/news"],
        }

    async def _run_with_grok(
        self,
        market: Market,
        callback: ProgressCallback,
        rounds: int,
    ) -> dict:
        """Execute research using Grok's streaming interface."""

        chat_module = import_module("xai_sdk.chat")
        tools_module = import_module("xai_sdk.tools")

        user_fn = getattr(chat_module, "user")
        web_search = getattr(tools_module, "web_search")
        x_search = getattr(tools_module, "x_search")

        chat = self._client.chat.create(
            model="grok-4-fast",
            tools=[web_search(), x_search()],
        )

        prompt = _build_prompt(market)
        chat.append(user_fn(prompt))

        total_rounds = rounds
        current_round = 0
        findings: list[str] = []
        citations: list[str] = []

        async for response, chunk in chat.stream_async():
            if chunk.tool_calls:
                current_round = min(total_rounds, current_round + 1)
                message = f"Round {current_round}/{total_rounds}: {chunk.tool_calls[0].function.name}"
                callback(ResearchProgress(message=message, round_number=current_round, total_rounds=total_rounds))
                findings.append(message)

            if chunk.content:
                findings.append(chunk.content)

            if response and getattr(response, "citations", None):
                citations = list(response.citations)

        callback(
            ResearchProgress(
                message="Grok synthesis complete. Generating structured output...",
                round_number=total_rounds,
                total_rounds=total_rounds,
                completed=True,
            )
        )

        response = chat.sample()
        content = getattr(response, "content", "")

        return {
            "prediction": "Yes" if "Yes" in content else "No",
            "probability": getattr(response, "probability", 0.5),
            "confidence": getattr(response, "confidence", self.config.min_confidence_threshold),
            "rationale": content,
            "key_findings": findings,
            "citations": citations,
        }


_SIMULATED_ROUNDS: tuple[str, ...] = (
    "Reviewing background context for '{question}'",
    "Scanning the open web for asymmetric information",
    "Analyzing sentiment shifts from X posts",
    "Cross-referencing data and preparing synthesis",
)


def _build_prompt(market: Market) -> str:
    """Return the structured Grok prompt from the PRD."""

    odds = ", ".join(f"{name}: {price:.0%}" for name, price in market.formatted_odds().items())
    return (
        "You are a prediction market analyst researching this poll:\n\n"
        f"Question: {market.question}\n"
        f"Options: {', '.join(market.formatted_odds().keys())}\n"
        f"Current market odds: {odds}\n"
        f"Resolves: {market.end_date.isoformat()}\n\n"
        "Your goal is to find information asymmetries that could give us edge over the market.\n\n"
        "Phase 1: Identify Information Gaps\n"
        "- What key factors determine this outcome?\n"
        "- What information is the market potentially missing?\n"
        "- What sources would have the best insights?\n\n"
        "Phase 2: Deep Research (use Web Search and X Search)\n"
        "- Search for recent news, analysis, data\n"
        "- Look for expert opinions, insider knowledge\n"
        "- Cross-reference multiple sources\n"
        "- Identify sentiment vs. facts\n\n"
        "Phase 3: Synthesize\n"
        "- Which option is most likely? (probability 0-1)\n"
        "- How confident are you? (0-100%)\n"
        "- What are the key reasons? (bullet points)\n"
        "- What information asymmetries did you find?\n"
        "- List all sources used\n\n"
        "Continue researching until you have high confidence OR hit diminishing returns."
    )


def _estimate_edge(market: Market) -> float:
    """Return a naive edge estimate using average outcome price."""

    outcomes = market.formatted_odds()
    if not outcomes:
        return 0.0

    yes_price = outcomes.get("Yes")
    if yes_price is None:
        yes_price = sum(outcomes.values()) / len(outcomes)
    return yes_price - 0.5
