# Multi-Agent Advisor System

> **3-role agent collaboration for cost-quoting decisions.** The point isn't
> the LLM — it's the orchestration: separation of concerns, quality gating,
> and surfacing intermediate artifacts.

---

## Why a Multi-Agent System?

Single-prompt LLMs fail in a specific way: they reason and retrieve and
self-evaluate in one pass, and you can't tell which step went wrong when the
output is bad. This system separates concerns so failures are debuggable:

```
   User query
       ↓
┌─────────────────┐
│ Intelligence    │  retrieves structured context from production DB
│   Agent         │  — no opinions, no recommendations
└────────┬────────┘
         ↓
┌─────────────────┐
│ Analysis        │  reasons over context, drafts a recommendation
│   Agent         │  — explicit assumptions, trade-offs, risks
└────────┬────────┘
         ↓
┌─────────────────┐
│ Critic          │  sanity-checks against bounds, citations,
│   Agent         │  risk coverage, trade-off honesty
└────────┬────────┘
         ↓
   Verdict + confidence + user-facing message
```

When a recommendation is bad, you know exactly which agent produced the bad
artifact. That's the entire reason for the separation.

---

## Design Trade-offs (explicit)

### Why 3 roles, not 5?

Each additional agent multiplies failure surface and debugging cost. 3 is the
minimum to demonstrate three distinct skills the system needs:
- Retrieval (Intelligence)
- Reasoning (Analysis)
- Quality gating (Critic)

A 5-agent design (e.g., add Pricing-Strategy and Customer-Profile agents)
would be more granular, but for a small factory's quoting use case, 3 is
sufficient. Scaling up is a deliberate decision triggered by complexity, not
a default.

### Why mock mode by default?

Two reasons:

1. **Reviewer-friendliness**: anyone cloning this repo can run the demo
   without an API key. The Multi-Agent *architecture* is the artifact — the
   LLM call is one possible implementation of each agent's interface.

2. **Cost / quota safety**: a public Streamlit Cloud demo that calls Claude API
   on every visitor click is a great way to burn through quota.

Toggle `Use real Claude API` in the sidebar (requires `ANTHROPIC_API_KEY` in
Streamlit Secrets) to switch any agent to real LLM mode.

### Why heterogeneous provider fallback (mock instead of retry)?

If the real Claude API call fails, we fall back to mock — not retry the same
provider. Retrying the same provider doesn't defend against the failure modes
that matter (provider outage, rate limit, model deprecation). Mock degradation
ensures the system stays *available*; "tried 3 times" doesn't.

This is the OpenClaw `cross-provider heterogeneous fallback chain` principle
applied at a smaller scale.

### Why surface intermediate artifacts to the UI?

A black-box LLM wrapper is unaccountable. A system that shows you each
agent's input and output is *debuggable* — which is the whole point of a
Multi-Agent design.

---

## Failure Modes (and how the system handles them)

| Failure Mode | How it's handled |
|---|---|
| Intelligence finds no matching orders | Returns empty arrays + explicit warning. Analysis Agent sees the empty context and refuses to recommend ("failing visibly beats failing silently"). |
| Analysis fabricates a price ungrounded in data | Critic Agent dimension 2 (citation integrity) flags the lack of `precheck/median` reference in rationale. |
| Analysis ignores BC flute known failure mode (49% MAPE) | Critic Agent dimension 3 (risk coverage) explicitly checks for MAPE/49 in risk descriptions when flute is BC. |
| LLM API call fails (network, quota, etc.) | `_real_call` catches the exception, returns mock with a notice. The user gets a recommendation either way. |
| Analysis says "everything is fine" | Critic Agent dimension 4 (trade-off honesty) flags the absence of trade-offs as suspicious. |

Each failure mode is tied to a specific Critic dimension — that's the
debuggable contract.

---

## File Layout

```
agents/
├── __init__.py              # Public API: exports the 4 classes
├── prompts.py               # System prompts for all 3 agents (real mode)
├── intelligence_agent.py    # 情报: retrieves structured context from SQLite
├── analysis_agent.py        # 分析: produces draft recommendation
├── critic_agent.py          # 审查: verdict + confidence + user message
└── orchestrator.py          # 编排: 3-step pipeline + intermediate artifact capture
```

---

## Quick Start (programmatic)

```python
from agents import AdvisorOrchestrator

# Mock mode (default, zero dependencies beyond the repo)
orch = AdvisorOrchestrator()
result = orch.advise("1L*12 瓶水剂出口纸箱，BC 瓦防水的，怎么报价？")

print(result["final_recommendation"])
# → {"price_per_m2": 1.4, "verdict": "approve", "confidence": 1.0, ...}

# Real Claude API mode (optional)
import os
orch = AdvisorOrchestrator(use_llm=True, api_key=os.environ["ANTHROPIC_API_KEY"])
result = orch.advise("...")
```

---

## What This Demonstrates (PM Lens)

For a portfolio reviewer:

| Skill | Where to see it |
|---|---|
| Multi-Agent orchestration | `orchestrator.py` — 3-step pipeline with intermediate artifacts surfaced |
| Prompt engineering with explicit input/output contracts | `prompts.py` — each system prompt declares the JSON schema it produces |
| Failure-mode coverage | `critic_agent.py` — 4 dimensions, each tied to a documented failure mode in this README |
| Graceful degradation | `analysis_agent.py:_real_call` and `critic_agent.py:_real_call` catch exceptions and fall back to mock |
| Separation of concerns | Intelligence is forbidden from reasoning; Analysis is forbidden from retrieval; Critic is forbidden from creating new recommendations |
| Honest disclosure of mode | Every output includes `"mode": "mock" | "real"` — users always know what they're looking at |

---

## What's NOT Here (Honest Scope)

- **No memory across queries** — each `advise()` call is stateless. A real
  production system would cache Intelligence retrievals and Critic decisions.
- **No drift monitoring** — when the underlying data shifts (new SKUs, new
  flute types), no agent automatically alerts. See main `EVAL_REPORT.md` §6
  for the planned `weekly_eval.py` drift monitor.
- **No tool use / function calling** — agents communicate via plain JSON
  schemas, not Claude tool use API. This is a deliberate simplicity choice;
  upgrade path is straightforward.

---

_Last updated: 2026-05-18_
