"""Multi-Agent AI Advisor System for yiwei-cost-engine.

Architecture: 3-role collaboration (Intelligence → Analysis → Critic),
orchestrated with provider-aware fallback chain (mock by default, optional
Claude API via Anthropic SDK).

See agents/README.md for the system design rationale.
"""
from .intelligence_agent import IntelligenceAgent
from .analysis_agent import AnalysisAgent
from .critic_agent import CriticAgent
from .orchestrator import AdvisorOrchestrator

__all__ = [
    "IntelligenceAgent",
    "AnalysisAgent",
    "CriticAgent",
    "AdvisorOrchestrator",
]
