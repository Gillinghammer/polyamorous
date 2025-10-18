"""Grok research orchestration for Poly."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
import inspect
from datetime import datetime, timezone
from importlib import import_module, util
from typing import Callable, Iterable, Optional

from ..config import ResearchConfig
from ..models import Market, ResearchProgress, ResearchResult

ProgressCallback = Callable[[ResearchProgress], None]


@dataclass
class ResearchService:
    """Coordinates multi-round Grok research."""

    config: ResearchConfig

    def __post_init__(self) -> None:
        self._client, self._is_async = self._build_client()

    async def conduct_research(
        self,
        market: Market,
        callback: ProgressCallback,
        rounds: int = 6,
    ) -> ResearchResult:
        """Run research asynchronously with Grok streaming and produce structured output."""

        start = datetime.now(tz=timezone.utc)

        if self._client is None:
            raise RuntimeError(
                "Grok client unavailable. Set XAI_API_KEY and install xai-sdk to enable research."
            )

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
        async_cls = getattr(module, "AsyncClient", None)
        if async_cls is None:
            raise RuntimeError("xai-sdk AsyncClient is required; install a recent xai-sdk.")
        return async_cls(api_key=api_key), True

    # Simulation removed by design; research requires Grok (xai-sdk + XAI_API_KEY)

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

        # Streaming via AsyncClient
        async for response, chunk in chat.stream():
            if getattr(chunk, "tool_calls", None):
                current_round = min(total_rounds, current_round + 1)
                message = f"Round {current_round}/{total_rounds}: {chunk.tool_calls[0].function.name}"
                callback(ResearchProgress(message=message, round_number=current_round, total_rounds=total_rounds))
                findings.append(message)

            if getattr(chunk, "content", None):
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

        # Retrieve final response
        response = await chat.sample()
        content = getattr(response, "content", "")

        parsed = _extract_json(content)
        if not parsed:
            parsed = {
                "prediction": "Yes" if "yes" in content.lower() else "No",
                "probability": 0.5,
                "confidence": float(self.config.min_confidence_threshold),
                "rationale": content[:2000],
                "key_findings": findings[-10:],
            }

        return {
            "prediction": str(parsed.get("prediction", "Yes")),
            "probability": float(parsed.get("probability", 0.5)),
            "confidence": float(parsed.get("confidence", self.config.min_confidence_threshold)),
            "rationale": str(parsed.get("rationale", ""))[:5000],
            "key_findings": list(parsed.get("key_findings", findings))[-20:],
            "citations": citations,
        }


def _build_prompt(market: Market) -> str:
    """Return a professional agentic research prompt optimized for Grok tools."""

    odds = ", ".join(f"{name}: {price:.0%}" for name, price in market.formatted_odds().items())
    options = ", ".join(market.formatted_odds().keys()) or "Yes, No"
    return (
        "You are a professional prediction market analyst. Your task is to research a Polymarket poll and surface asymmetric information that the market may be missing.\n\n"
        f"Poll Question: {market.question}\n"
        f"Options: {options}\n"
        f"Current Market Odds: {odds}\n"
        f"Resolves At: {market.end_date.isoformat()}\n\n"
        "Use server-side tools aggressively: web_search() for news/analysis/data and x_search() for real-time sentiment and insider knowledge.\n"
        "Prioritize: primary sources, expert analysis, recent developments, credible leaks/insider signals.\n"
        "Evaluate sentiment vs facts, detect narrative shifts, and identify crowd wisdom patterns on X (accounts, communities, engagement).\n"
        "Look for catalysts, timelines, dependencies, and leading indicators.\n\n"
        "Working style:\n"
        "- Iterate in multiple rounds.\n"
        "- Cross-check claims.\n"
        "- Note unknowns and failure modes.\n"
        "- Stop only when information is saturated or diminishing returns.\n\n"
        "At the end, output ONLY a compact JSON object with keys: \n"
        "{\"prediction\": string (the option most likely), \n"
        " \"probability\": number (0-1), \n"
        " \"confidence\": number (0-100), \n"
        " \"rationale\": string (concise synthesis), \n"
        " \"key_findings\": string[] (5-10 bullets).}\n"
        "Do not include any extra text outside the JSON."
    )


def _extract_json(text: str) -> dict | None:
    """Extract and parse a JSON object from arbitrary model output."""

    import json
    import re

    if not text:
        return None
    # Remove code fences if present
    cleaned = re.sub(r"```(json)?", "", text).strip()
    # Find the last JSON-like object in the string
    match = re.search(r"\{[\s\S]*\}$", cleaned)
    if not match:
        # Try a more liberal search for any JSON object
        match = re.search(r"\{[\s\S]*\}", cleaned)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except Exception:
        return None
