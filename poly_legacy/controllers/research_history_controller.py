from __future__ import annotations

from typing import Dict, List, Tuple


class ResearchHistoryController:
    def build_history_rows(self, rows: List[dict], question_by_market_id: Dict[str, str]) -> List[Tuple[str, ...]]:
        view_rows: List[Tuple[str, ...]] = []
        for r in rows:
            q = question_by_market_id.get(r["market_id"], r["market_id"])[:60]
            q = q + ("…" if len(q) == 60 else "")
            rec = r.get("rec") or "-"
            dec = r.get("decision") or "-"
            edge = f"{float(r.get('edge') or 0.0):+0.2f}"
            date = str(r.get("created_at"))[:16]
            view_rows.append((q, rec.capitalize(), dec.capitalize() if isinstance(dec, str) else "-", edge, date, r["market_id"]))
        return view_rows


