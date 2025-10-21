"""SQLite persistence for research results."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from polly.models import ResearchResult


SCHEMA = """
CREATE TABLE IF NOT EXISTS research (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_id TEXT NOT NULL UNIQUE,
    prediction TEXT NOT NULL,
    probability REAL NOT NULL,
    confidence REAL NOT NULL,
    rationale TEXT NOT NULL,
    key_findings TEXT NOT NULL,
    citations TEXT NOT NULL,
    rounds_completed INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    duration_minutes INTEGER NOT NULL,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    reasoning_tokens INTEGER,
    estimated_cost_usd REAL,
    eval_edge REAL,
    eval_recommendation TEXT,
    user_decision TEXT,
    decision_at TEXT
);
"""


class ResearchRepository:
    """Handles persistence of research results by market."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(SCHEMA)
            self._ensure_columns(connection)

    def _ensure_columns(self, connection: sqlite3.Connection) -> None:
        """Add missing schema columns for backward compatibility."""
        info = connection.execute("PRAGMA table_info(research)").fetchall()
        names = {row[1] for row in info}
        to_add: list[tuple[str, str]] = []
        if "user_decision" not in names:
            to_add.append(("user_decision", "TEXT"))
        if "decision_at" not in names:
            to_add.append(("decision_at", "TEXT"))
        for col, col_type in to_add:
            connection.execute(f"ALTER TABLE research ADD COLUMN {col} {col_type}")

    def upsert_result(
        self,
        result: ResearchResult,
        eval_edge: float,
        eval_recommendation: str,
    ) -> None:
        """Insert or replace a research result for a market."""

        payload = asdict(result)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO research (
                    market_id, prediction, probability, confidence, rationale,
                    key_findings, citations, rounds_completed, created_at,
                    duration_minutes, prompt_tokens, completion_tokens, reasoning_tokens,
                    estimated_cost_usd, eval_edge, eval_recommendation
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(market_id) DO UPDATE SET
                    prediction=excluded.prediction,
                    probability=excluded.probability,
                    confidence=excluded.confidence,
                    rationale=excluded.rationale,
                    key_findings=excluded.key_findings,
                    citations=excluded.citations,
                    rounds_completed=excluded.rounds_completed,
                    created_at=excluded.created_at,
                    duration_minutes=excluded.duration_minutes,
                    prompt_tokens=excluded.prompt_tokens,
                    completion_tokens=excluded.completion_tokens,
                    reasoning_tokens=excluded.reasoning_tokens,
                    estimated_cost_usd=excluded.estimated_cost_usd,
                    eval_edge=excluded.eval_edge,
                    eval_recommendation=excluded.eval_recommendation
                """,
                (
                    payload["market_id"],
                    payload["prediction"],
                    payload["probability"],
                    payload["confidence"],
                    payload["rationale"],
                    json.dumps(payload["key_findings"]),
                    json.dumps(payload["citations"]),
                    payload["rounds_completed"],
                    payload["created_at"].isoformat(),
                    payload["duration_minutes"],
                    payload["prompt_tokens"],
                    payload["completion_tokens"],
                    payload["reasoning_tokens"],
                    payload["estimated_cost_usd"],
                    float(eval_edge),
                    str(eval_recommendation),
                ),
            )

    def set_decision(self, market_id: str, decision: str) -> None:
        """Persist a user decision (enter/pass) for a researched market."""
        now_iso = datetime.utcnow().isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE research
                SET user_decision = ?, decision_at = ?
                WHERE market_id = ?
                """,
                (decision, now_iso, market_id),
            )

    def get_decision(self, market_id: str) -> Optional[str]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT user_decision FROM research WHERE market_id = ?",
                (market_id,),
            ).fetchone()
        if not row:
            return None
        return row[0]

    def get_by_market_id(self, market_id: str) -> Optional[tuple[ResearchResult, float, str]]:
        """Return persisted research result and evaluation for a market, if any.

        Returns a tuple of (ResearchResult, eval_edge, eval_recommendation) or None.
        """

        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM research WHERE market_id = ?
                """,
                (market_id,),
            ).fetchone()
        if not row:
            return None
        return self._row_to_result(row)

    def has_research(self, market_id: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM research WHERE market_id = ?",
                (market_id,),
            ).fetchone()
        return bool(row)

    def list(self, decision: str = "all") -> list[dict]:
        """Return basic research rows for history display.

        decision: "all" | "undecided" | "decided"
        """
        where = ""
        if decision == "undecided":
            where = "WHERE user_decision IS NULL"
        elif decision == "decided":
            where = "WHERE user_decision IS NOT NULL"
        with self._connect() as connection:
            cursor = connection.execute(
                f"""
                SELECT market_id, created_at, eval_edge, eval_recommendation, user_decision
                FROM research
                {where}
                ORDER BY datetime(created_at) DESC
                """
            )
            rows = cursor.fetchall()
        out: list[dict] = []
        for r in rows:
            out.append(
                {
                    "market_id": r["market_id"],
                    "created_at": r["created_at"],
                    "edge": r["eval_edge"],
                    "rec": r["eval_recommendation"],
                    "decision": r["user_decision"],
                }
            )
        return out

    def _row_to_result(self, row: sqlite3.Row) -> tuple[ResearchResult, float, str]:
        key_findings = json.loads(row["key_findings"]) if row["key_findings"] else []
        citations = json.loads(row["citations"]) if row["citations"] else []
        return (
            ResearchResult(
                market_id=row["market_id"],
                prediction=row["prediction"],
                probability=row["probability"],
                confidence=row["confidence"],
                rationale=row["rationale"],
                key_findings=key_findings,
                citations=citations,
                rounds_completed=row["rounds_completed"],
                created_at=datetime.fromisoformat(row["created_at"]),
                duration_minutes=row["duration_minutes"],
                prompt_tokens=row["prompt_tokens"],
                completion_tokens=row["completion_tokens"],
                reasoning_tokens=row["reasoning_tokens"],
                estimated_cost_usd=row["estimated_cost_usd"],
            ),
            float(row["eval_edge"]) if row["eval_edge"] is not None else 0.0,
            str(row["eval_recommendation"]) if row["eval_recommendation"] else "pass",
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        return connection


