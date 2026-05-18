"""Analysis Agent · 分析推理层

Consumes Intelligence Agent's structured context, produces a draft recommendation
with explicit assumptions and trade-offs.

Modes:
- Mock (default): Heuristic-driven recommendation based on context stats.
- Real: Calls Claude API (Anthropic SDK) with ANALYSIS_SYSTEM_PROMPT.

Both modes return the same output schema → Critic Agent doesn't care which one ran.
"""
from typing import Optional

from .prompts import ANALYSIS_SYSTEM_PROMPT, MOCK_INTELLIGENCE_NOTICE


class AnalysisAgent:
    """Reasons over Intelligence context to produce a draft recommendation."""

    def __init__(self, use_llm: bool = False, api_key: Optional[str] = None, model: str = "claude-opus-4-7"):
        self.use_llm = use_llm and bool(api_key)
        self.model = model
        self._client = None
        if self.use_llm:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=api_key)
            except ImportError:
                self.use_llm = False  # Fallback to mock if SDK unavailable

    def recommend(self, context: dict, query: str) -> dict:
        """Main entry: produce draft recommendation. Same schema mock vs real."""
        if not context.get("similar_orders"):
            return self._cannot_recommend(context)

        if self.use_llm and self._client:
            return self._real_call(context, query)
        return self._mock_call(context, query)

    # ------------------------------------------------------------------ modes

    def _mock_call(self, context: dict, query: str) -> dict:
        """Heuristic recommendation: median price + flute risk surfacing.

        This is intentionally simple — the point is to demonstrate the contract,
        not to be a good pricing model (we have eval_runner.py for that).
        """
        price_range = context.get("price_range", {})
        flute_filter = context.get("flute_filter")
        warnings = context.get("warnings", [])

        suggested = price_range.get("p50")
        if suggested is None:
            return self._cannot_recommend(context)

        assumptions = [f"Quoting based on median of {price_range.get('n', 0)} comparable precheck records"]
        if flute_filter:
            assumptions.append(f"Assuming {flute_filter} flute, standard lamination")

        risks = []
        if flute_filter and "BC" in flute_filter:
            risks.append({
                "risk": "BC flute baseline systematically underestimates by ~49% MAPE",
                "severity": "high",
                "mitigation": "Defer pricing to human review for waterproof variants, or apply +30-50% premium",
            })
        if context.get("n_matches", 0) < 5:
            risks.append({
                "risk": f"Low sample size (n={context.get('n_matches', 0)})",
                "severity": "medium",
                "mitigation": "Quote conservatively at p75 instead of p50, or widen search criteria",
            })

        trade_offs = [
            f"Quoting at p50 (¥{suggested}/m²) balances win-rate and margin. "
            f"Aggressive (p25=¥{price_range.get('p25')}/m²) wins more deals but compresses margin "
            f"by ~{round((suggested - price_range['p25']) / suggested * 100)}% vs median."
            if price_range.get('p25') else "Insufficient data for aggressive-pricing trade-off analysis."
        ]

        return {
            "agent": "analysis",
            "mode": "mock",
            "notice": MOCK_INTELLIGENCE_NOTICE,
            "assumptions": assumptions,
            "recommended_price_per_m2": suggested,
            "rationale": f"Median of {price_range.get('n', 0)} precheck records is the most defensible "
                         f"starting point. p25-p75 range ¥{price_range.get('p25')}-¥{price_range.get('p75')} "
                         f"reflects the actual market spread.",
            "trade_offs": trade_offs,
            "risks": risks,
            "warnings_from_intelligence": warnings,
        }

    def _real_call(self, context: dict, query: str) -> dict:
        """Calls Claude API with structured context."""
        import json
        user_msg = (
            f"User query: {query}\n\n"
            f"Intelligence Agent's context (JSON):\n{json.dumps(context, ensure_ascii=False, indent=2)}\n\n"
            "Produce your recommendation strictly in the JSON schema specified."
        )

        try:
            resp = self._client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=ANALYSIS_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_msg}],
            )
            text = resp.content[0].text
            # Try to parse the JSON from the response
            parsed = self._extract_json(text)
            parsed["agent"] = "analysis"
            parsed["mode"] = "real"
            parsed["model"] = self.model
            parsed["warnings_from_intelligence"] = context.get("warnings", [])
            return parsed
        except Exception as e:
            # Provider fallback: degrade to mock with a note
            mock = self._mock_call(context, query)
            mock["notice"] = f"⚠️ Real LLM call failed ({type(e).__name__}: {e}). Fell back to mock."
            return mock

    # ------------------------------------------------------------------ helpers

    def _cannot_recommend(self, context: dict) -> dict:
        return {
            "agent": "analysis",
            "mode": "mock",
            "assumptions": [],
            "recommended_price_per_m2": None,
            "rationale": "Cannot recommend: Intelligence Agent returned no comparable orders. "
                         "Failing visibly beats failing silently.",
            "trade_offs": [],
            "risks": [{
                "risk": "Insufficient historical data",
                "severity": "high",
                "mitigation": "Manually quote based on raw cost calculation + human judgment",
            }],
            "warnings_from_intelligence": context.get("warnings", []),
        }

    def _extract_json(self, text: str) -> dict:
        """Best-effort JSON extraction from LLM output."""
        import json, re
        if m := re.search(r"\{.*\}", text, re.DOTALL):
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
        return {"raw_text": text, "parse_failed": True}
