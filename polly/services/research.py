from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Callable, Optional

from ..config import Config
from ..db import Database

log = logging.getLogger(__name__)


@dataclass
class ResearchResult:
    id: str
    recommendation: str
    confidence: float
    position_size_pct: float
    rationale: str
    citations: List[Dict[str, Any]]


ProgressCallback = Callable[[str], None]


class ResearchService:
    def __init__(self, cfg: Config, db: Database) -> None:
        self.cfg = cfg
        self.db = db

    def run_research_stream(self, poll_id: str, question: str, callback: Optional[ProgressCallback] = None) -> ResearchResult:
        """Run Grok research with streaming updates (sync client in a worker thread).

        Fails fast if xai-sdk or XAI_API_KEY is missing.
        """
        if not self.cfg.xai_api_key:
            raise RuntimeError("XAI_API_KEY is required to run research")

        try:
            from xai_sdk import Client  # type: ignore
            from xai_sdk.chat import user  # type: ignore
            from xai_sdk.tools import web_search, x_search  # type: ignore
            try:
                # Optional tool; include when available
                from xai_sdk.tools import code_execution  # type: ignore
            except Exception:
                code_execution = None  # type: ignore
        except Exception as exc:
            raise RuntimeError("xai-sdk is required to run research") from exc

        client = Client(api_key=self.cfg.xai_api_key)
        tools = [web_search(), x_search()]
        try:
            if code_execution is not None:  # type: ignore[name-defined]
                tools.append(code_execution())
        except Exception:
            # Ignore if the SDK doesn't support code_execution
            pass
        chat = client.chat.create(model="grok-4-fast", tools=tools)

        prompt = self._build_prompt(question)
        chat.append(user(prompt))

        started_at = int(time.time())
        citations: List[str] = []
        findings: List[str] = []
        final_response = None

        if callback:
            callback("Starting Grok research…")

        # Stream responses and tool calls
        for response, chunk in chat.stream():
            final_response = response
            try:
                tool_calls = getattr(chunk, "tool_calls", None)
                if tool_calls:
                    func = tool_calls[0].function
                    msg = f"{func.name}: {str(func.arguments)[:100]}"
                    findings.append(msg)
                    if callback:
                        callback(msg)
                if getattr(chunk, "content", None):
                    findings.append(chunk.content)
            except Exception:
                pass

        if final_response and getattr(final_response, "citations", None):
            try:
                citations = list(final_response.citations)
            except Exception:
                citations = []

        content = getattr(final_response, "content", "") if final_response else ""
        parsed = self._extract_json(content)
        if not parsed:
            parsed = {
                "recommendation": "enter",
                "confidence": 0.70,
                "position_size_pct": 0.10,
                "rationale": content[:1000] or "No structured rationale provided.",
            }

        # Map citations to structured list for DB
        structured_citations: List[Dict[str, Any]] = []
        now = int(time.time())
        for url in citations[:10]:
            structured_citations.append({
                "kind": "web" if "x.com" not in url else "x",
                "title": None,
                "url": url,
                "snippet": None,
                "source": None,
                "published_at": now,
            })

        research_id = str(uuid.uuid4())
        completed_at = int(time.time())

        with self.db.as_conn() as conn:
            conn.execute(
                """
                INSERT INTO research(id, poll_id, started_at, completed_at, recommendation, confidence, position_size_pct, rationale, provider, meta_json)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    research_id,
                    poll_id,
                    started_at,
                    completed_at,
                    str(parsed.get("recommendation", "enter")),
                    float(parsed.get("confidence", 0.7)),
                    float(parsed.get("position_size_pct", 0.10)),
                    str(parsed.get("rationale", ""))[:5000],
                    "grok4",
                    json.dumps({"version": 1}),
                ),
            )
            for c in structured_citations:
                cid = str(uuid.uuid4())
                conn.execute(
                    """
                    INSERT INTO citations(id, research_id, kind, title, url, snippet, source, published_at)
                    VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        cid,
                        research_id,
                        c["kind"],
                        c.get("title"),
                        c["url"],
                        c.get("snippet"),
                        c.get("source"),
                        c.get("published_at"),
                    ),
                )

        log.info("research_saved", extra={"poll_id": poll_id, "research_id": research_id})
        if callback:
            callback("Research complete.")
        return ResearchResult(
            id=research_id,
            recommendation=str(parsed.get("recommendation", "enter")),
            confidence=float(parsed.get("confidence", 0.7)),
            position_size_pct=float(parsed.get("position_size_pct", 0.10)),
            rationale=str(parsed.get("rationale", ""))[:5000],
            citations=structured_citations,
        )

    @staticmethod
    def _build_prompt(question: str) -> str:
        """Return an agentic prompt optimized for Grok tools with structured output.

        The model should plan topics first, use web_search/x_search aggressively, weight X sources by credibility
        and engagement, tie synthesis to odds/catalysts/timelines, and finally emit ONLY compact JSON for our schema.
        """
        return (
            "You are a professional prediction market analyst. Your job is to research a Polymarket poll and surface\n"
            "asymmetric information the market may be missing. Work in tight loops and keep output concise.\n\n"
            f"Poll Question: {question}\n\n"
            "Meta plan first (do not skip): Generate 5-8 research topics that could materially change implied odds.\n"
            "For each topic, specify whether to use web_search, x_search, or both, and why. Then execute.\n\n"
            "X-source weighting: Identify qualified voices on X (credentials, past track record). Incorporate engagement\n"
            "signals (likes/reposts/replies/quotes) as soft evidence of salience, not truth. Assign a trust score (0-1)\n"
            "combining author credibility and engagement quality. Prioritize diverse perspectives and credible contrarian takes.\n\n"
            "Tool usage: Use server-side tools aggressively — web_search() for mainstream sources and x_search() for real-time\n"
            "nuance and insider signals. When quantitative checks are needed, prefer code execution rather than estimation.\n\n"
            "Synthesis requirements (tie to odds): Convert findings into a probability for the most likely option (0-1),\n"
            "compare to current market odds, and highlight catalysts/timelines that could move odds before resolution.\n\n"
            "Return ONLY a compact JSON object with keys: {\"recommendation\": 'enter'|'pass', \"confidence\": 0-1,\n"
            "\"position_size_pct\": 0-1, \"rationale\": string}. Do not include any extra text outside the JSON."
        )

    @staticmethod
    def _extract_json(text: str) -> dict | None:
        import re
        if not text:
            return None
        cleaned = re.sub(r"```(json)?", "", text).strip()
        match = re.search(r"\{[\s\S]*\}$", cleaned)
        if not match:
            match = re.search(r"\{[\s\S]*\}", cleaned)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except Exception:
            return None


