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
from polly.models import Market, MarketGroup, MarketRecommendation, ResearchProgress, ResearchResult

ProgressCallback = Callable[[ResearchProgress], None]


class ResearchTracker:
    """Tracks information density during research to detect saturation."""
    
    def __init__(self):
        self.unique_domains = set()
        self.all_citations = []
        self.rounds_since_new_domain = 0
        self.tool_usage = {}
    
    def add_citation(self, url: str) -> bool:
        """Add citation and return True if from a new domain.
        
        Args:
            url: Citation URL
            
        Returns:
            True if this is a new unique domain, False if repeat
        """
        from urllib.parse import urlparse
        
        self.all_citations.append(url)
        
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            # Remove www. prefix
            domain = domain.replace('www.', '')
            
            if domain and domain not in self.unique_domains:
                self.unique_domains.add(domain)
                self.rounds_since_new_domain = 0
                return True
            else:
                self.rounds_since_new_domain += 1
                return False
        except Exception:
            return False
    
    def record_tool_call(self, tool_name: str) -> None:
        """Record a tool usage."""
        self.tool_usage[tool_name] = self.tool_usage.get(tool_name, 0) + 1
    
    def is_saturated(self) -> bool:
        """Check if research has hit diminishing returns.
        
        Returns True if:
        - 5+ rounds without new domains
        - OR 10+ total citations with low diversity
        """
        if self.rounds_since_new_domain >= 5:
            return True
        
        # Check diversity: if we have 10+ citations but only 2-3 domains, might be saturated
        if len(self.all_citations) >= 10 and len(self.unique_domains) <= 3:
            return True
        
        return False
    
    def get_stats(self) -> dict:
        """Get research statistics."""
        return {
            "unique_domains": len(self.unique_domains),
            "total_citations": len(self.all_citations),
            "tool_usage": dict(self.tool_usage),
            "information_density": len(self.unique_domains) / max(len(self.all_citations), 1),
        }


def calculate_optimal_rounds(group: MarketGroup) -> int:
    """Calculate optimal research rounds based on event characteristics.
    
    Scales rounds based on:
    - Number of candidates (complexity)
    - Market uncertainty (no clear favorite)
    - Liquidity (market attention/sophistication)
    
    Returns:
        Optimal round count (10-30)
    """
    base_rounds = 10
    
    # Add rounds for complexity
    num_candidates = len(group.markets)
    if num_candidates > 50:
        base_rounds += 15  # 25 rounds for 128-candidate events
    elif num_candidates > 20:
        base_rounds += 10  # 20 rounds for 30-candidate events
    elif num_candidates > 5:
        base_rounds += 5   # 15 rounds for 10-candidate events
    # else: 10 rounds for simple 2-6 candidate events
    
    # Add rounds for high uncertainty (no clear favorite)
    top_3 = group.get_top_markets(3)
    if top_3:
        # Get Yes probability for top candidate
        top_outcomes = top_3[0].outcomes
        top_prob = 0.0
        for outcome in top_outcomes:
            if outcome.outcome.lower() in ('yes', 'y'):
                top_prob = outcome.price
                break
        
        if top_prob < 0.5:  # No candidate above 50%
            base_rounds += 5  # +5 rounds for uncertain race
    
    # Add rounds for high liquidity (more market attention = more to research)
    if group.liquidity > 5_000_000:
        base_rounds += 5  # +5 rounds for $5M+ events
    
    return min(base_rounds, 30)  # Cap at 30 rounds


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
    
    async def research_market_group(
        self,
        group: MarketGroup,
        callback: ProgressCallback,
        rounds: int | None = None,
    ) -> ResearchResult:
        """Research a grouped multi-outcome event and recommend multiple positions."""
        
        start = datetime.now(tz=timezone.utc)

        if util.find_spec("xai_sdk") is None or not os.getenv("XAI_API_KEY"):
            raise RuntimeError(
                "Grok client unavailable. Set XAI_API_KEY and install xai-sdk to enable research."
            )
        chosen_rounds = int(rounds) if rounds is not None else int(self.config.default_rounds)

        result = await self._run_group_research_with_grok(group, callback, chosen_rounds)

        duration = datetime.now(tz=timezone.utc) - start
        
        # Parse recommendations from result
        recommendations = []
        for rec_data in result.get("recommendations", []):
            # Clamp confidence to 0-100 range (handle cases where model returns raw number)
            raw_conf = float(rec_data.get("confidence", 70.0))
            if raw_conf > 100:
                raw_conf = raw_conf / 100.0
            clamped_conf = max(0.0, min(100.0, raw_conf))
            
            recommendations.append(MarketRecommendation(
                market_id=rec_data.get("market_id", ""),
                market_question=rec_data.get("market_question", ""),
                prediction=rec_data.get("prediction", "Yes"),
                probability=float(rec_data.get("probability", 0.5)),
                confidence=clamped_conf,
                rationale=rec_data.get("rationale", ""),
                entry_suggested=rec_data.get("entry_suggested", False),
                suggested_stake=float(rec_data.get("suggested_stake", 100.0)),
            ))
        
        # Use primary recommendation for backward compatibility
        primary = recommendations[0] if recommendations else None
        
        # Build key findings that include tracker stats
        key_findings_with_stats = list(result["key_findings"])
        
        # Add tracker stats to key findings for display (since we can't add attributes to slots=True dataclass)
        if result.get("unique_domains", 0) > 0:
            key_findings_with_stats.insert(0, f"Research quality: {result.get('unique_domains')} unique sources, {result.get('information_density', 0):.0%} information density")
        
        return ResearchResult(
            market_id=group.id,  # Use group ID
            prediction=primary.prediction if primary else "PASS",
            probability=primary.probability if primary else 0.0,
            confidence=primary.confidence if primary else 0.0,
            rationale=result["rationale"],
            key_findings=key_findings_with_stats,
            citations=result["citations"],
            rounds_completed=chosen_rounds,
            created_at=start,
            duration_minutes=max(1, int(duration.total_seconds() // 60)),
            prompt_tokens=result.get("prompt_tokens"),
            completion_tokens=result.get("completion_tokens"),
            reasoning_tokens=result.get("reasoning_tokens"),
            estimated_cost_usd=result.get("estimated_cost_usd"),
            event_id=group.id,
            is_grouped=True,
            recommendations=recommendations,
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
    
    def _estimate_cost(
        self,
        prompt_tokens: int | None,
        completion_tokens: int | None,
        reasoning_tokens: int | None,
    ) -> float | None:
        """Estimate USD cost based on token usage and configured prices."""
        try:
            cost = 0.0
            if prompt_tokens and self.config.prompt_token_price_per_1k:
                cost += (float(prompt_tokens) / 1000.0) * float(self.config.prompt_token_price_per_1k)
            if completion_tokens and self.config.completion_token_price_per_1k:
                cost += (float(completion_tokens) / 1000.0) * float(self.config.completion_token_price_per_1k)
            if reasoning_tokens and self.config.reasoning_token_price_per_1k:
                cost += (float(reasoning_tokens) / 1000.0) * float(self.config.reasoning_token_price_per_1k)
            return round(cost, 6) if cost > 0 else None
        except Exception:
            return None

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

        # Clamp confidence to valid 0-100 range (handle cases where Grok returns percentage as decimal or out of range)
        raw_confidence = float(parsed.get("confidence", self.config.min_confidence_threshold))
        if raw_confidence > 100:
            # If > 100, assume it was given as a percentage already (e.g., 7500 instead of 75)
            # Try dividing by 100 first
            raw_confidence = raw_confidence / 100
        # Clamp to 0-100 range
        confidence = max(0.0, min(100.0, raw_confidence))
        
        result = {
            "prediction": str(parsed.get("prediction", "Yes")),
            "probability": float(parsed.get("probability", 0.5)),
            "confidence": confidence,
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
    
    async def _run_group_research_with_grok(
        self,
        group: MarketGroup,
        callback: ProgressCallback,
        rounds: int,
    ) -> dict:
        """Execute research on a grouped multi-outcome event using Grok."""
        
        chat_module = import_module("xai_sdk.chat")
        tools_module = import_module("xai_sdk.tools")

        user_fn = getattr(chat_module, "user")
        web_search = getattr(tools_module, "web_search")
        x_search = getattr(tools_module, "x_search")
        code_exec = getattr(tools_module, "code_execution", None)

        client = self._build_client()
        if not client:
            raise RuntimeError("Grok client not available")

        # Build tool instances (same pattern as _run_with_grok)
        tool_instances = []
        ws_kwargs = {"enable_image_understanding": bool(self.config.enable_image_understanding)}
        xs_kwargs = {
            "enable_image_understanding": bool(self.config.enable_image_understanding),
            "enable_video_understanding": bool(self.config.enable_video_understanding),
        }
        tool_instances.append(web_search(**ws_kwargs))
        tool_instances.append(x_search(**xs_kwargs))

        if self.config.enable_code_execution and code_exec is not None:
            tool_instances.append(code_exec())

        # Create chat session
        chat = client.chat.create(
            model=str(self.config.model_name or "grok-4-fast"),
            tools=tool_instances,
        )

        # Build and append initial prompt
        prompt = _build_group_prompt(group, self.config, rounds)
        chat.append(user_fn(prompt))
        
        current_round = 0
        findings = []
        citations = []
        tracker = ResearchTracker()  # Track information saturation
        
        from time import monotonic
        from urllib.parse import urlparse
        import json as _json
        
        final_response = None
        last_reasoning_bucket = -1
        last_usage_emit = 0.0
        tool_counts = {}
        
        # Emit start message
        callback(ResearchProgress(
            message=f"Starting Grok group research ({self.config.model_name}); tools: web_search, x_search",
            round_number=0,
            total_rounds=rounds,
        ))
        
        first_event_seen = False
        stop_heartbeat = False
        
        # Add heartbeat for initial feedback
        async def _heartbeat() -> None:
            while not stop_heartbeat:
                callback(ResearchProgress(
                    message="Research running… awaiting first tool call",
                    round_number=max(0, current_round),
                    total_rounds=rounds,
                ))
                await asyncio.sleep(3)
        
        hb_task = asyncio.create_task(_heartbeat())
        
        # Stream responses (matching _run_with_grok pattern)
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
                    current_round = min(rounds, current_round + 1)
                    try:
                        func = chunk.tool_calls[0].function
                        tool_counts[func.name] = tool_counts.get(func.name, 0) + 1
                        tracker.record_tool_call(func.name)  # Track tool usage
                        
                        # Get query/arguments preview
                        args_preview = ""
                        try:
                            args_obj = _json.loads(func.arguments) if isinstance(func.arguments, str) else func.arguments
                            query = (
                                (args_obj.get("query") if isinstance(args_obj, dict) else None)
                                or (args_obj.get("q") if isinstance(args_obj, dict) else None)
                                or str(func.arguments)
                            )
                            args_preview = str(query) if query else str(func.arguments)
                        except Exception:
                            args_preview = str(func.arguments)
                        
                        if len(args_preview) > 120:
                            args_preview = args_preview[:117] + "..."
                        
                        message = f"Round {current_round}/{rounds}: {func.name} — {args_preview}"
                    except Exception:
                        message = f"Round {current_round}/{rounds}: tool_call"
                    
                    callback(ResearchProgress(
                        message=message,
                        round_number=current_round,
                        total_rounds=rounds,
                    ))
                    findings.append(message)
                
                # Process content
                if getattr(chunk, "content", None):
                    findings.append(chunk.content)
                
                # Track citations
                if response and getattr(response, "citations", None):
                    new_citations = list(response.citations)
                    if len(new_citations) > len(citations):
                        for cite in new_citations[len(citations):]:
                            # Track in ResearchTracker
                            is_new_domain = tracker.add_citation(cite)
                            
                            # Show if new domain or just repeat source
                            if is_new_domain:
                                callback(ResearchProgress(
                                    message=f"📎 Found: {cite}",
                                    round_number=current_round,
                                    total_rounds=rounds,
                                ))
                            
                            try:
                                parsed_url = urlparse(cite)
                                if parsed_url.netloc:
                                    citations.append(cite)
                            except Exception:
                                pass
                
                # Check for saturation and warn
                if tracker.is_saturated() and current_round < rounds:
                    callback(ResearchProgress(
                        message=f"ℹ️  Information saturation detected ({tracker.rounds_since_new_domain} rounds without new sources)",
                        round_number=current_round,
                        total_rounds=rounds,
                    ))
                
                final_response = response
        
        except Exception as e:
            callback(ResearchProgress(
                message=f"Error during research: {str(e)}",
                round_number=current_round,
                total_rounds=rounds,
            ))
        finally:
            # Stop heartbeat if still running
            stop_heartbeat = True
            try:
                hb_task.cancel()
            except Exception:
                pass
            
            # Emit completion
            callback(ResearchProgress(
                message=f"Research completed after {current_round} rounds",
                round_number=current_round,
                total_rounds=rounds,
                completed=True,
            ))
        
        # Parse final response
        final_text = getattr(final_response, "content", "") if final_response else ""
        
        # Debug: Check what we got
        if current_round == 0:
            if final_response:
                # Research completed without tool calls - likely got immediate response
                callback(ResearchProgress(
                    message=f"⚠️  Model responded without using research tools. Response length: {len(final_text)}",
                    round_number=0,
                    total_rounds=rounds,
                ))
            else:
                callback(ResearchProgress(
                    message="⚠️  No response received from model",
                    round_number=0,
                    total_rounds=rounds,
                ))
        
        # Try to extract JSON from final response
        parsed = _extract_json(final_text)
        
        if parsed and isinstance(parsed, dict):
            recommendations = parsed.get("recommendations", [])
            rationale = parsed.get("rationale", final_text[:500])
            key_findings = parsed.get("key_findings", [])
            citations_from_json = parsed.get("citations", [])
            # Merge with citations found during streaming
            citations_list = list(set(citations + citations_from_json))
        else:
            # Fallback if JSON parsing fails
            recommendations = []
            # Use the full text if we have findings, otherwise use final_text
            if findings:
                rationale = "\n".join(findings)[:500]
            else:
                rationale = final_text[:500] if final_text else "Group research completed without tool usage"
            key_findings = ["Research completed", f"Rounds executed: {current_round}"]
            citations_list = list(citations)
        
        # Get usage stats
        usage = getattr(final_response, "usage", None) if final_response else None
        prompt_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
        completion_tokens = getattr(usage, "completion_tokens", 0) if usage else 0
        reasoning_tokens = getattr(usage, "reasoning_tokens", 0) if usage else 0
        
        # Get tracker statistics
        tracker_stats = tracker.get_stats()
        
        # Close client
        try:
            await client.close()
        except Exception:
            pass
        
        return {
            "recommendations": recommendations,
            "rationale": rationale,
            "key_findings": key_findings,
            "citations": citations_list,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "reasoning_tokens": reasoning_tokens,
            "estimated_cost_usd": self._estimate_cost(
                prompt_tokens,
                completion_tokens,
                reasoning_tokens
            ),
            # Research quality metrics
            "unique_domains": tracker_stats["unique_domains"],
            "total_citations": tracker_stats["total_citations"],
            "tool_usage": tracker_stats["tool_usage"],
            "information_density": tracker_stats["information_density"],
        }


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

    description = market.description.strip() if market.description else "No additional details provided."
    resolution_source = market.resolution_source.strip() if market.resolution_source else "Not specified"
    
    return (
        "You are a professional prediction market analyst. Your task is to research a Polymarket poll and surface asymmetric information that the market may be missing.\n\n"
        f"Poll Question: {market.question}\n"
        f"Resolution Source: {resolution_source}\n"
        f"Description & Resolution Criteria: {description}\n"
        f"Options: {options}\n"
        f"Current Market Odds: {odds}\n"
        f"Resolves At: {market.end_date.isoformat()}\n\n"
        "CRITICAL: Pay special attention to the Resolution Source above - this is the EXACT source that will determine the outcome. Your research must focus on what this specific source will report, not what you think should happen or what other sources might say. Understand how this source operates, their methodology, timing, and any edge cases in their reporting.\n\n"
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


def _build_group_prompt(group: MarketGroup, config: ResearchConfig, total_rounds: int) -> str:
    """Build research prompt for grouped multi-outcome events."""
    
    # Get top candidates by Yes probability (winning odds)
    top_markets = group.get_top_markets(10)
    candidates_info = []
    for market in top_markets:
        # Get Yes probability
        yes_prob = next((o.price for o in market.outcomes if o.outcome.lower() in ('yes', 'y')), 0.0)
        # Extract candidate name from question
        candidate = market.question.split("Will ")[-1].split(" win")[0] if "Will " in market.question else market.question
        candidates_info.append(f"  • {candidate}: {yes_prob:.1%} (${market.liquidity:,.0f} liquidity)")
    
    candidates_str = "\n".join(candidates_info)
    
    topic_range = f"{config.topic_count_min}-{config.topic_count_max}"
    
    description = group.description.strip() if group.description else "No additional details provided."
    resolution_source = group.resolution_source.strip() if group.resolution_source else "Not specified"
    
    return (
        "You are a professional prediction market analyst researching a MULTI-OUTCOME event on Polymarket.\n\n"
        f"Event Question: {group.title}\n"
        f"Resolution Source: {resolution_source}\n"
        f"Description & Resolution Criteria: {description}\n"
        f"Total Candidates: {len(group.markets)}\n"
        f"Event Liquidity: ${group.liquidity:,.0f}\n"
        f"Resolves At: {group.end_date.isoformat()}\n\n"
        f"Top 10 Candidates by Current Market Odds (Yes = chance to win):\n{candidates_str}\n\n"
        "CRITICAL: Pay attention to the Resolution Source - this determines the outcome. Focus research on what this specific source will report.\n\n"
        "YOUR GOAL: Find asymmetric information to identify:\n"
        "1. Who is MOST LIKELY to win (primary prediction)\n"
        "2. Any UNDERVALUED candidates (market too pessimistic)\n"
        "3. Any OVERVALUED candidates (market too optimistic)\n\n"
        f"Meta plan first (DO NOT SKIP THIS STEP): Generate a concise list of "
        f"{topic_range} research topics/questions that would materially impact who wins. "
        "For each topic, specify whether to use web_search, x_search, or both.\n\n"
        "CRITICAL - YOU MUST USE TOOLS: Do not answer based on training data alone. You MUST:\n"
        "- Call web_search() multiple times for recent news, polls, expert analysis\n"
        "- Call x_search() multiple times for real-time sentiment and insider signals\n"
        "- Research each viable candidate individually\n"
        "- Cross-reference multiple sources\n"
        "- The research will be worthless if you don't use these tools extensively\n\n"
        "RESEARCH STRATEGY BY PHASE:\n"
        f"- Phase 1 (Rounds 1-{max(5, total_rounds//4)}): Broad discovery - Get mainstream polls, news, expert takes\n"
        f"- Phase 2 (Rounds {max(6, total_rounds//4+1)}-{max(12, total_rounds*2//3)}): Deep dive - X sentiment, insider signals, browse detailed sources\n"
        f"- Phase 3 (Rounds {max(13, total_rounds*2//3+1)}-{total_rounds}): Validation & edge finding - Confirm analysis, find final value plays\n\n"
        "RESEARCH SUCCESS METRICS (aim for all of these):\n"
        "- Find at least 1 position with >15% edge vs market odds\n"
        "- Identify 2-3 undervalued candidates for portfolio hedge\n"
        "- Collect 10+ unique high-quality citations from diverse sources\n"
        "- Achieve >80% confidence in primary prediction\n"
        "- Generate portfolio with combined EV >100% of stake\n\n"
        "COMMON PITFALLS TO AVOID:\n"
        "- Don't just bet on the favorite (look for undervalued alternatives!)\n"
        "- Don't ignore longshots with massive edge (0.1% → 5% = 50x edge)\n"
        "- Don't rely on outdated polls (prioritize last 2 weeks)\n"
        "- Don't miss sentiment shifts on X (often leads polls)\n"
        "- Don't overlook candidates with low liquidity but high potential\n\n"
        "STOPPING CRITERIA:\n"
        f"- You may stop BEFORE round {total_rounds} if:\n"
        "  • Achieved >90% confidence AND last 3 rounds yielded redundant info\n"
        "  • Covered all viable candidates (>1% odds) thoroughly\n"
        "  • Found clear edge opportunities with positive EV\n"
        f"- You SHOULD use all {total_rounds} rounds if:\n"
        "  • Finding contradictory information that needs resolution\n"
        "  • Each round still yielding new insights\n"
        "  • Discovering undervalued candidates with positive EV\n"
        "  • Race is uncertain or odds are shifting\n\n"
        "Working style:\n"
        "- Research each viable candidate (>1% odds) individually\n"
        "- Cross-check claims and flag contradictions\n"
        "- Look for undervalued longshots or second-place contenders\n"
        "- If one candidate heavily favored (>80%), research others for hedge value\n\n"
        "PORTFOLIO OPTIMIZATION: You should recommend positions on MULTIPLE candidates (1-5) when:\n"
        "- There are multiple viable contenders → hedge reduces variance\n"
        "- You find undervalued candidates with positive EV\n"
        "- Combined positions improve risk-adjusted returns\n\n"
        "POSITION SIZING: Allocate capital proportionally based on:\n"
        "- Edge size (probability vs market odds)\n"
        "- Confidence level\n"
        "- Liquidity available\n"
        "- Kelly criterion or similar for optimal sizing\n\n"
        "Example strategy: If total budget is $500:\n"
        "- Primary pick (60% edge): $300 stake\n"
        "- Hedge pick (20% edge): $150 stake  \n"
        "- Value longshot (10% edge): $50 stake\n"
        "This diversifies risk while maintaining positive EV.\n\n"
        "At the end of your research (after all rounds), output ONLY a compact JSON object:\n"
        "{\n"
        '  "prediction": "<most likely winner name>",\n'
        '  "probability": <0-1 for winner>,\n'
        '  "confidence": <0-100>,\n'
        '  "rationale": "<overall strategy and why these positions work together>",\n'
        '  "key_findings": ["finding 1", "finding 2", "finding 3", "finding 4", "finding 5"],\n'
        '  "recommendations": [\n'
        '    {"market_id": "<conditionId>", "market_question": "<full question>", "prediction": "Yes", "probability": 0.0-1.0, "confidence": 0-100, "rationale": "<why this position>", "entry_suggested": true, "suggested_stake": 300.0},\n'
        '    {"market_id": "<conditionId>", "market_question": "<full question>", "prediction": "Yes", "probability": 0.0-1.0, "confidence": 0-100, "rationale": "<why this position>", "entry_suggested": true, "suggested_stake": 150.0},\n'
        '    {"market_id": "<conditionId>", "market_question": "<full question>", "prediction": "Yes", "probability": 0.0-1.0, "confidence": 0-100, "rationale": "<why as hedge>", "entry_suggested": true, "suggested_stake": 50.0}\n'
        "  ]\n"
        "}\n\n"
        'The "suggested_stake" field is important - it should reflect the relative strength of each position in your overall strategy.\n'
        "Do not include any extra text outside the JSON in your final output."
    )
