"""Advisor Orchestrator · 编排层

Coordinates the 3-role Multi-Agent collaboration. Trade-offs explicitly chosen:

1. **3 roles, not 5**: Each additional Agent multiplies failure surface and
   debugging cost. 3 (Intelligence → Analysis → Critic) is the minimum to
   demonstrate separation of concerns + quality gating.

2. **Heterogeneous provider fallback chain**: When real LLM calls fail, drop
   to mock instead of retrying the same provider — single-provider retry doesn't
   defend against provider outages, mock degradation does.

3. **Surface intermediate artifacts**: The UI shows every Agent's output, not
   just the final answer. This is the difference between a black-box wrapper
   and a debuggable system.
"""
from typing import Optional
import time

from .intelligence_agent import IntelligenceAgent
from .analysis_agent import AnalysisAgent
from .critic_agent import CriticAgent


class AdvisorOrchestrator:
    """3-role Multi-Agent advisor: Intelligence → Analysis → Critic."""

    def __init__(
        self,
        db_path: Optional[str] = None,
        use_llm: bool = False,
        api_key: Optional[str] = None,
        model: str = "claude-opus-4-7",
    ):
        self.intelligence = IntelligenceAgent(db_path=db_path)
        self.analysis = AnalysisAgent(use_llm=use_llm, api_key=api_key, model=model)
        self.critic = CriticAgent(use_llm=use_llm, api_key=api_key, model=model)
        self.use_llm = use_llm and bool(api_key)

    def advise(self, query: str, flute_hint: Optional[str] = None) -> dict:
        """Main entry: run 3-agent pipeline and return structured result.

        Returns a dict with full intermediate artifacts — the UI is expected to
        render each agent's output so the user sees the reasoning chain, not
        just the final answer.
        """
        result = {
            "query": query,
            "use_llm": self.use_llm,
            "timestamps": {},
        }

        # ----- Step 1: Intelligence gathers context -----
        t0 = time.time()
        context = self.intelligence.gather(query, flute_hint=flute_hint)
        result["intelligence"] = context
        result["timestamps"]["intelligence_ms"] = round((time.time() - t0) * 1000)

        # ----- Step 2: Analysis produces draft -----
        t0 = time.time()
        draft = self.analysis.recommend(context, query)
        result["analysis"] = draft
        result["timestamps"]["analysis_ms"] = round((time.time() - t0) * 1000)

        # ----- Step 3: Critic reviews -----
        t0 = time.time()
        verdict = self.critic.review(context, draft, query)
        result["critic"] = verdict
        result["timestamps"]["critic_ms"] = round((time.time() - t0) * 1000)

        # ----- Final composite -----
        result["final_recommendation"] = self._compose_final(draft, verdict)
        result["total_ms"] = sum(result["timestamps"].values())

        return result

    def _compose_final(self, draft: dict, verdict: dict) -> dict:
        """Compose the user-facing final answer with the Critic's verdict."""
        return {
            "price_per_m2": draft.get("recommended_price_per_m2") if verdict["verdict"] != "reject" else None,
            "verdict": verdict["verdict"],
            "confidence": verdict["confidence"],
            "message_to_user": verdict["recommendation_to_user"],
        }
