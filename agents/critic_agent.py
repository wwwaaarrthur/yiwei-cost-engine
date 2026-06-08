"""Critic Agent · 审查 / 质量门禁

Last line of defense before a recommendation reaches the user. Checks the
Analysis Agent's draft against sanity bounds, citation integrity, risk coverage,
and trade-off honesty.

Verdict: approve / revise / reject (with confidence score).

Same as AnalysisAgent: mock by default, real Claude API optional.
"""
from typing import Optional

from .prompts import CRITIC_SYSTEM_PROMPT


class CriticAgent:
    """Reviews Analysis Agent's draft and returns a verdict + confidence."""

    def __init__(self, use_llm: bool = False, api_key: Optional[str] = None,
                 model: Optional[str] = None, provider: str = "deepseek"):
        from .llm_client import LLMClient
        self.use_llm = use_llm
        self.provider = provider
        self._llm = LLMClient(provider=provider, model=model, api_key=api_key) if use_llm else None
        # effective model is whatever the client resolved to (may have degraded to mock)
        self.model = self._llm.model if self._llm else "mock"

    def review(self, context: dict, draft: dict, query: str) -> dict:
        """Main entry: review draft → return verdict + recommendation_to_user."""
        if self.use_llm and self._llm and self._llm.provider != "mock":
            return self._real_call(context, draft, query)
        return self._mock_call(context, draft, query)

    # ------------------------------------------------------------------ modes

    def _mock_call(self, context: dict, draft: dict, query: str) -> dict:
        """Rule-based critic. Checks 4 dimensions explicitly."""
        issues = []
        confidence = 1.0

        # Dimension 1: Sanity bounds (price within p25-p75)
        price_range = context.get("price_range", {})
        recommended = draft.get("recommended_price_per_m2")
        if recommended is None:
            return self._reject_no_data(draft)

        p25, p75 = price_range.get("p25"), price_range.get("p75")
        if p25 and p75:
            if recommended < p25 * 0.8:
                issues.append({
                    "type": "sanity_bounds",
                    "detail": f"Recommended ¥{recommended}/m² is significantly below p25 (¥{p25}). "
                              f"Aggressive pricing — flag for margin review.",
                    "severity": "high",
                })
                confidence -= 0.3
            elif recommended > p75 * 1.2:
                issues.append({
                    "type": "sanity_bounds",
                    "detail": f"Recommended ¥{recommended}/m² is significantly above p75 (¥{p75}). "
                              f"Premium pricing — verify customer can absorb.",
                    "severity": "medium",
                })
                confidence -= 0.2

        # Dimension 2: Citation integrity (did Analysis use real data?)
        if "rationale" in draft and "precheck" not in draft["rationale"].lower() and "median" not in draft["rationale"].lower():
            issues.append({
                "type": "citation_integrity",
                "detail": "Analysis's rationale doesn't explicitly cite source data (median/precheck records).",
                "severity": "low",
            })
            confidence -= 0.1

        # Dimension 3: Risk coverage (BC flute warning when relevant)
        flute = context.get("flute_filter", "")
        risk_descriptions = " ".join([r.get("risk", "") for r in draft.get("risks", [])])
        if flute and "BC" in flute and "MAPE" not in risk_descriptions and "49" not in risk_descriptions:
            issues.append({
                "type": "risk_coverage",
                "detail": "BC flute query but Analysis did not flag the known 49% MAPE failure mode.",
                "severity": "high",
            })
            confidence -= 0.3

        # Dimension 4: Trade-off honesty
        if not draft.get("trade_offs"):
            issues.append({
                "type": "trade_off_honesty",
                "detail": "No trade-offs articulated. Recommendation that says 'everything is fine' is suspicious.",
                "severity": "medium",
            })
            confidence -= 0.2

        # Determine verdict
        if confidence >= 0.8:
            verdict = "approve"
        elif confidence >= 0.5:
            verdict = "revise"
        else:
            verdict = "reject"

        return {
            "agent": "critic",
            "mode": "mock",
            "verdict": verdict,
            "confidence": round(max(0.0, confidence), 2),
            "issues": issues,
            "recommendation_to_user": self._compose_user_message(verdict, draft, issues),
        }

    def _real_call(self, context: dict, draft: dict, query: str) -> dict:
        """Calls the configured LLM (DeepSeek) via LLMClient; falls back to mock on any failure."""
        import json
        user_msg = (
            f"Original user query: {query}\n\n"
            f"Intelligence context:\n{json.dumps(context, ensure_ascii=False, indent=2)}\n\n"
            f"Analysis draft:\n{json.dumps(draft, ensure_ascii=False, indent=2)}\n\n"
            "Review per the four dimensions in your system prompt. Output strict JSON."
        )
        text, trace = self._llm.chat(CRITIC_SYSTEM_PROMPT, user_msg)
        if text is None:                       # mock / degraded / failed
            out = self._mock_call(context, draft, query)
            out["trace"] = trace
            return out
        parsed = self._extract_json(text)
        # Normalize verdict to the allowed enum — a real LLM may phrase it freely
        # ("needs revision", "Rejected", "APPROVE") and we must not count that as invalid.
        raw_v = str(parsed.get("verdict", "")).lower()
        if "approv" in raw_v:
            parsed["verdict"] = "approve"
        elif "revis" in raw_v:
            parsed["verdict"] = "revise"
        elif "reject" in raw_v:
            parsed["verdict"] = "reject"
        parsed.update({"agent": "critic", "mode": "real", "model": self.model, "trace": trace})
        return parsed

    # ------------------------------------------------------------------ helpers

    def _reject_no_data(self, draft: dict) -> dict:
        return {
            "agent": "critic",
            "mode": "mock",
            "verdict": "reject",
            "confidence": 0.95,
            "issues": [{
                "type": "no_data",
                "detail": "Analysis Agent could not produce a recommendation due to insufficient context.",
                "severity": "high",
            }],
            "recommendation_to_user": "Cannot quote with current data. Required actions: "
                                       "(1) widen search keywords, (2) manually input dimensions, "
                                       "(3) escalate to senior worker for one-off pricing.",
        }

    def _compose_user_message(self, verdict: str, draft: dict, issues: list) -> str:
        price = draft.get("recommended_price_per_m2")
        if verdict == "approve":
            return f"✅ Recommended price: ¥{price}/m². Verdict: approved with no major issues."
        if verdict == "revise":
            issue_summary = "; ".join([i["detail"] for i in issues[:2]])
            return f"⚠️ Suggested price: ¥{price}/m², BUT review caveats: {issue_summary}"
        return f"🛑 Cannot approve recommendation. Issues: {'; '.join([i['detail'] for i in issues])}"

    def _extract_json(self, text: str) -> dict:
        import json, re
        if m := re.search(r"\{.*\}", text, re.DOTALL):
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
        return {"raw_text": text, "parse_failed": True}
