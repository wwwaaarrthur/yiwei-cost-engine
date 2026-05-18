"""Intelligence Agent · 情报收集层

Single responsibility: retrieve and structure historical context from the
production database. Does NOT reason, recommend, or interpret.

The output schema is the contract with the Analysis Agent — see prompts.py.
"""
import os
import sqlite3
import statistics
import re
from typing import Optional


def _default_db_path() -> str:
    """Resolve DB path the same way app.py does — prod first, demo fallback."""
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(here)
    prod = os.path.join(repo_root, "data", "process_sheets.db")
    demo = os.path.join(repo_root, "data", "demo.db")
    return prod if os.path.exists(prod) else demo


class IntelligenceAgent:
    """Retrieves and structures historical context for a quoting query."""

    def __init__(self, db_path: Optional[str] = None, top_k: int = 10):
        self.db_path = db_path or _default_db_path()
        self.top_k = top_k

    def gather(self, query: str, flute_hint: Optional[str] = None) -> dict:
        """Main entry: parse query → retrieve similar orders → return structured context.

        The returned dict is the input contract for AnalysisAgent.
        Failure mode: empty arrays + explicit warnings (never hallucinate).
        """
        if not os.path.exists(self.db_path):
            return self._empty_context(f"Database not found: {self.db_path}")

        keywords = self._extract_keywords(query)
        flute_filter = flute_hint or self._guess_flute(query)

        try:
            similar = self._query_similar_orders(keywords, flute_filter)
        except sqlite3.Error as e:
            return self._empty_context(f"DB query failed: {e}")

        if not similar:
            return self._empty_context(
                f"No matching orders for keywords={keywords} flute={flute_filter}"
            )

        return {
            "agent": "intelligence",
            "query": query,
            "keywords_extracted": keywords,
            "flute_filter": flute_filter,
            "similar_orders": similar[: self.top_k],
            "n_matches": len(similar),
            "price_range": self._price_stats(similar),
            "flute_breakdown": self._flute_breakdown(similar),
            "warnings": self._compile_warnings(similar, flute_filter),
        }

    # ------------------------------------------------------------------ helpers

    def _extract_keywords(self, query: str) -> list:
        """Pull product/spec keywords from natural-language query."""
        keywords = []
        if m := re.search(r"\d+L[*x×]\d+瓶?", query):
            keywords.append(m.group())
        if m := re.search(r"\d+kg[*x×]?\d*袋?", query):
            keywords.append(m.group())
        for tag in ("水剂", "颗粒", "外贸", "出口", "桔子箱", "草莓"):
            if tag in query:
                keywords.append(tag)
        return keywords

    def _guess_flute(self, query: str) -> Optional[str]:
        q = query.upper()
        for flute in ("BC", "EB", "BE", "E瓦", "B瓦", "单E"):
            if flute.upper() in q:
                return flute.upper().replace("瓦", "")
        return None

    def _query_similar_orders(self, keywords: list, flute_filter: Optional[str]) -> list:
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        sql = "SELECT product, client, flute_type, board_w, board_h, order_qty FROM process_sheets WHERE error IS NULL"
        params = []
        if keywords:
            sql += " AND (" + " OR ".join(["product LIKE ?"] * len(keywords)) + ")"
            params.extend([f"%{k}%" for k in keywords])
        if flute_filter:
            sql += " AND flute_type LIKE ?"
            params.append(f"%{flute_filter}%")
        sql += " LIMIT 200"

        rows = cur.execute(sql, params).fetchall()
        conn.close()

        return [
            {
                "product": r[0],
                "client": r[1],
                "flute_type": r[2],
                "board_dims_mm": f"{r[3]}x{r[4]}" if r[3] and r[4] else None,
                "order_qty": r[5],
                "area_m2_per_unit": (r[3] * r[4] / 1_000_000) if r[3] and r[4] else None,
            }
            for r in rows
        ]

    def _price_stats(self, orders: list) -> dict:
        """Without unit cost in process_sheets, derive a proxy from precheck_costs."""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        try:
            costs = [
                r[0] for r in cur.execute(
                    "SELECT unit_cost FROM precheck_costs WHERE unit_cost > 0 AND unit_cost < 50"
                ).fetchall()
            ]
        except sqlite3.Error:
            costs = []
        conn.close()

        if not costs:
            return {"p25": None, "p50": None, "p75": None, "n": 0, "currency": "CNY/m²"}

        costs.sort()
        n = len(costs)
        return {
            "p25": round(costs[n // 4], 2),
            "p50": round(costs[n // 2], 2),
            "p75": round(costs[3 * n // 4], 2),
            "n": n,
            "currency": "CNY/m²",
        }

    def _flute_breakdown(self, orders: list) -> dict:
        """Group orders by flute type with counts."""
        breakdown = {}
        for o in orders:
            ft = (o.get("flute_type") or "未知").strip()
            breakdown[ft] = breakdown.get(ft, 0) + 1
        return breakdown

    def _compile_warnings(self, orders: list, flute_filter: Optional[str]) -> list:
        warnings = []
        if flute_filter and "BC" in flute_filter:
            warnings.append(
                "BC flute: baseline pricing model has MAPE 49.1%, Bias -0.928. "
                "Recommendation: defer pricing to human review or apply +30-50% premium "
                "for waterproof/specialty variants (see EVAL_REPORT.md §2)."
            )
        if len(orders) < 5:
            warnings.append(
                f"Low sample size (n={len(orders)}). "
                "Recommendation: widen keyword filter or quote conservatively."
            )
        return warnings

    def _empty_context(self, reason: str) -> dict:
        return {
            "agent": "intelligence",
            "query": "",
            "keywords_extracted": [],
            "flute_filter": None,
            "similar_orders": [],
            "n_matches": 0,
            "price_range": {"p25": None, "p50": None, "p75": None, "n": 0, "currency": "CNY/m²"},
            "flute_breakdown": {},
            "warnings": [f"No data: {reason}"],
        }
