"""Grok research orchestration for Polly."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
import inspect
from datetime import datetime, timezone
from importlib import import_module, util
from typing import Callable, Iterable, Optional

from polly.config import ResearchConfig
from polly.models import Market, ResearchProgress, ResearchResult

ProgressCallback = Callable[[ResearchProgress], None]


@dataclass
class ResearchService:
    """Coordinates multi-round Grok research."""

    config: ResearchConfig

    def __post_init__(self) -> None:
        # Avoid retaining a client across threads/event loops.
        # We'll instantiate an AsyncClient inside the research worker.
        pass

    async def conduct_research(
        self,
        market: Market,
        callback: ProgressCallback,
        rounds: int | None = None,
    ) -> ResearchResult:
        """Run research asynchronously with Grok streaming and produce structured output."""

        start = datetime.now(tz=timezone.utc)

        if util.find_spec("xai_sdk") is None or not os.getenv("XAI_API_KEY"):
            raise RuntimeError(
                "Grok client unavailable. Set XAI_API_KEY and install xai-sdk to enable research."
            )
        chosen_rounds = int(rounds) if rounds is not None else int(self.config.default_rounds)

        result = await self._run_with_grok(market, callback, chosen_rounds)

        duration = datetime.now(tz=timezone.utc) - start
        return ResearchResult(
            market_id=market.id,
            prediction=result["prediction"],
            probability=result["probability"],
            confidence=result["confidence"],
            rationale=result["rationale"],
            key_findings=result["key_findings"],
            citations=result["citations"],
            rounds_completed=chosen_rounds,
            created_at=start,
            duration_minutes=max(1, int(duration.total_seconds() // 60)),
            prompt_tokens=result.get("prompt_tokens"),
            completion_tokens=result.get("completion_tokens"),
            reasoning_tokens=result.get("reasoning_tokens"),
            estimated_cost_usd=result.get("estimated_cost_usd"),
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
        return async_cls(api_key=api_key)

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
        code_exec = getattr(tools_module, "code_execution", None)

        client = self._build_client()

        tool_instances = []
        # Use unfiltered tools to encourage diverse discovery, with optional media understanding
        ws_kwargs = {"enable_image_understanding": bool(self.config.enable_image_understanding)}
        xs_kwargs = {
            "enable_image_understanding": bool(self.config.enable_image_understanding),
            "enable_video_understanding": bool(self.config.enable_video_understanding),
        }
        tool_instances.append(web_search(**ws_kwargs))
        tool_instances.append(x_search(**xs_kwargs))

        # Optional code execution
        if self.config.enable_code_execution and code_exec is not None:
            tool_instances.append(code_exec())

        chat = client.chat.create(
            model=str(self.config.model_name or "grok-4-fast"),
            tools=tool_instances,
        )

        total_rounds = rounds
        prompt = _build_prompt(market, self.config, total_rounds)
        chat.append(user_fn(prompt))
        current_round = 0
        findings: list[str] = []
        citations: list[str] = []

        # Streaming via AsyncClient; keep track of the last response
        from time import monotonic
        from urllib.parse import urlparse
        import json as _json

        final_response = None
        last_reasoning_bucket = -1
        last_usage_emit = 0.0
        tool_counts: dict[str, int] = {}

        # Emit immediate start message and a heartbeat until first event
        callback(ResearchProgress(
            message=(
                f"Starting Grok research ({self.config.model_name}); tools: web_search, x_search"
                + (", code_execution" if self.config.enable_code_execution else "")
                + f"; rounds: {total_rounds}"
            ),
            round_number=0,
            total_rounds=total_rounds,
        ))

        first_event_seen = False
        stop_heartbeat = False

        async def _heartbeat() -> None:
            while not stop_heartbeat:
                callback(ResearchProgress(
                    message="Research running… awaiting first tool call",
                    round_number=max(0, current_round),
                    total_rounds=total_rounds,
                ))
                await asyncio.sleep(3)

        hb_task = asyncio.create_task(_heartbeat())

        try:
            async for response, chunk in chat.stream():
                if not first_event_seen:
                    first_event_seen = True
                    stop_heartbeat = True
                    try:
                        hb_task.cancel()
                    except Exception:
                        pass
                
                # Process tool calls
                if getattr(chunk, "tool_calls", None):
                    current_round = min(total_rounds, current_round + 1)
                    try:
                        func = chunk.tool_calls[0].function
                        tool_counts[func.name] = tool_counts.get(func.name, 0) + 1

                        # Prefer a human-friendly preview from args
                        args_preview = ""
                        try:
                            args_obj = _json.loads(func.arguments) if isinstance(func.arguments, str) else func.arguments
                            query = (
                                (args_obj.get("query") if isinstance(args_obj, dict) else None)
                                or (args_obj.get("q") if isinstance(args_obj, dict) else None)
                                or (args_obj.get("keywords") if isinstance(args_obj, dict) else None)
                                or (args_obj.get("text") if isinstance(args_obj, dict) else None)
                            )
                            args_preview = str(query) if query else str(func.arguments)
                        except Exception:
                            args_preview = str(func.arguments)
                        if len(args_preview) > 120:
                            args_preview = args_preview[:117] + "..."
                        message = f"Round {current_round}/{total_rounds}: {func.name} — {args_preview}"
                    except Exception:
                        message = f"Round {current_round}/{total_rounds}: tool_call"
                    callback(ResearchProgress(message=message, round_number=current_round, total_rounds=total_rounds))
                    findings.append(message)

                    # Periodic usage summary (every ~3s)
                    now = monotonic()
                    if now - last_usage_emit > 3.0:
                        summary = ", ".join(f"{k}:{v}" for k, v in tool_counts.items())
                        callback(ResearchProgress(
                            message=f"Usage so far: {summary}",
                            round_number=current_round,
                            total_rounds=total_rounds,
                        ))
                        last_usage_emit = now

                # Process content chunks
                if getattr(chunk, "content", None):
                    findings.append(chunk.content)

                # Throttled thinking progress
                usage = getattr(response, "usage", None)
                if usage and getattr(usage, "reasoning_tokens", None):
                    bucket = int(usage.reasoning_tokens) // 200
                    if bucket > last_reasoning_bucket:
                        last_reasoning_bucket = bucket
                        callback(ResearchProgress(
                            message=f"Thinking... ({usage.reasoning_tokens} reasoning tokens)",
                            round_number=current_round,
                            total_rounds=total_rounds,
                        ))

                # Collect citations as they appear
                if response and getattr(response, "citations", None):
                    new_citations = list(response.citations)
                    # Emit new citations incrementally
                    if len(new_citations) > len(citations):
                        for cite in new_citations[len(citations):]:
                            callback(ResearchProgress(
                                message=f"📎 Found: {cite}",
                                round_number=current_round,
                                total_rounds=total_rounds,
                            ))
                    citations = new_citations
                
                final_response = response

        finally:
            stop_heartbeat = True
            try:
                hb_task.cancel()
            except Exception:
                pass

        # Final usage summary if available
        final_message = "Grok synthesis complete. Generating structured output..."
        try:
            usage_summary = getattr(final_response, "server_side_tool_usage", None)
            if usage_summary:
                final_message += f" Tools used: {dict(usage_summary)}"
        except Exception:
            pass

        callback(ResearchProgress(
            message=final_message,
            round_number=total_rounds,
            total_rounds=total_rounds,
            completed=True,
        ))

        # Emit top citations with domains for transparency
        if citations:
            callback(ResearchProgress(
                message="Top citations:",
                round_number=total_rounds,
                total_rounds=total_rounds,
            ))
            for url in citations[:10]:
                try:
                    domain = urlparse(url).netloc or url
                except Exception:
                    domain = url
                callback(ResearchProgress(
                    message=f"- {domain} — {url}",
                    round_number=total_rounds,
                    total_rounds=total_rounds,
                ))

        # Retrieve final content from the streamed response (avoid extra call)
        content = getattr(final_response, "content", "")

        parsed = _extract_json(content)
        if not parsed:
            parsed = {
                "prediction": "Yes" if "yes" in content.lower() else "No",
                "probability": 0.5,
                "confidence": float(self.config.min_confidence_threshold),
                "rationale": content[:2000],
                "key_findings": findings[-10:],
            }

        # Usage and cost estimation (best-effort; fields may vary by SDK version)
        usage = getattr(final_response, "usage", None)
        prompt_tokens = getattr(usage, "prompt_tokens", None) if usage else None
        completion_tokens = getattr(usage, "completion_tokens", None) if usage else None
        reasoning_tokens = getattr(usage, "reasoning_tokens", None) if usage else None

        estimated_cost = None
        try:
            cost = 0.0
            if prompt_tokens and self.config.prompt_token_price_per_1k:
                cost += (float(prompt_tokens) / 1000.0) * float(self.config.prompt_token_price_per_1k)
            if completion_tokens and self.config.completion_token_price_per_1k:
                cost += (float(completion_tokens) / 1000.0) * float(self.config.completion_token_price_per_1k)
            if reasoning_tokens and self.config.reasoning_token_price_per_1k:
                cost += (float(reasoning_tokens) / 1000.0) * float(self.config.reasoning_token_price_per_1k)
            estimated_cost = round(cost, 6)
        except Exception:
            estimated_cost = None

        result = {
            "prediction": str(parsed.get("prediction", "Yes")),
            "probability": float(parsed.get("probability", 0.5)),
            "confidence": float(parsed.get("confidence", self.config.min_confidence_threshold)),
            "rationale": str(parsed.get("rationale", ""))[:5000],
            "key_findings": list(parsed.get("key_findings", findings))[-20:],
            "citations": citations,
            "prompt_tokens": int(prompt_tokens) if isinstance(prompt_tokens, (int, float)) else None,
            "completion_tokens": int(completion_tokens) if isinstance(completion_tokens, (int, float)) else None,
            "reasoning_tokens": int(reasoning_tokens) if isinstance(reasoning_tokens, (int, float)) else None,
            "estimated_cost_usd": estimated_cost,
        }

        # Close client to prevent pending tasks on loop shutdown
        try:
            await client.close()
        except Exception:
            pass

        return result


def _build_prompt(market: Market, config: ResearchConfig, total_rounds: int) -> str:
    """Return a professional agentic research prompt optimized for Grok tools.

    Includes meta topic planning, X-source weighting, and odds-relative synthesis.
    """

    odds = ", ".join(f"{name}: {price:.0%}" for name, price in market.formatted_odds().items())
    options = ", ".join(market.formatted_odds().keys()) or "Yes, No"
    # Scoping removed by default for broader discovery
    domain_scope = ""
    x_scope = ""

    topic_range = f"{config.topic_count_min}-{config.topic_count_max}"

    return (
        "You are a professional prediction market analyst. Your task is to research a Polymarket poll and surface asymmetric information that the market may be missing.\n\n"
        f"Poll Question: {market.question}\n"
        f"Options: {options}\n"
        f"Current Market Odds: {odds}\n"
        f"Resolves At: {market.end_date.isoformat()}\n\n"
        "Meta plan first (do not skip): Generate a concise list of "
        f"{topic_range} research topics/questions that, if answered, would materially change implied odds. "
        "For each topic, specify whether to use web_search, x_search, or both, and why.\n\n"
        "X-source weighting: Identify qualified voices on X (credentials, domain expertise, past track record). "
        "Incorporate engagement signals (likes, reposts, replies, quote-tweets) as soft evidence of salience, not truth. "
        "Assign a trust score (0-1) combining author credibility and engagement quality. Prioritize diverse perspectives and surface contrarian but credible takes.\n\n"
        "Tool usage: Use server-side tools aggressively: web_search() for mainstream sources and x_search() for real-time nuance and insider signals.\n\n"
        "When quantitative checks are needed (e.g., averages, regressions, aggregation), call code_execution to compute and verify rather than estimating.\n\n"
        "Working style:\n"
        f"- Iterate in multiple rounds (target: {total_rounds}).\n"
        "- Cross-check claims and flag contradictions.\n"
        "- Note unknowns and failure modes.\n"
        "- Stop only when information is saturated or diminishing returns.\n\n"
        "Synthesis requirements (tie to odds):\n"
        "- Convert findings into a probability for the most likely option (0-1).\n"
        "- Compare to current market odds; highlight where mainstream vs X perspectives diverge and why.\n"
        "- Call out catalysts/timelines that can move odds before resolution.\n\n"
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
