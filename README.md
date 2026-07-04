# Yiwei Cost Engine

> **A digital-transformation case study: turning a 10-year-old factory's tacit pricing knowledge into a verifiable, auditable, AI-evaluated system.**
> Not a model demo — a product-judgment record. Built and decided end-to-end by one person acting as the AI Product Manager, not the algorithm engineer.

[![Built with Streamlit](https://img.shields.io/badge/Built%20with-Streamlit-FF4B4B?logo=streamlit)](https://streamlit.io)
[![Python 3.14](https://img.shields.io/badge/Python-3.14-blue?logo=python)](https://www.python.org)
[![SQLite](https://img.shields.io/badge/Storage-SQLite-003B57?logo=sqlite)](https://sqlite.org)

[**🚀 Live Demo · yiwei-cost-engine.streamlit.app**](https://yiwei-cost-engine.streamlit.app)

Public zero-login render verified on 2026-07-04; evidence is stored outside this public repo at `memory/evidence/streamlit-public-verified-20260704.png`.

---

## For Recruiters / Interviewers — the 60-second version

This project demonstrates **AI Product Management / Digital Transformation judgment**, not model training. The thing I am most proud of is **not** an accuracy number — it is the **evaluation system** that makes every pricing decision measurable, auditable, and safe to iterate. Two product decisions define it:

1. **I built a 7-piece evaluation harness** for a real product (the part most AI side-projects skip). See it first, below.
2. **I deliberately did NOT let an LLM set prices.** Contract amounts need auditability and zero hallucination, so pricing stays deterministic. AI is used where uncertainty is real — explanation, risk review, missing-info detection — never for the final price. Knowing *when not to use AI* is the judgment this project is really about.

Deep-dive paths: [the eval system](#-ai-evaluation-system-what-i-built-as-the-pm) · [why pricing avoids an LLM](#-the-pm-judgment-why-pricing-does-not-use-an-llm) · [EVAL_REPORT.md](EVAL_REPORT.md) · [NORTH_STAR_PROOF_MAP.md](docs/NORTH_STAR_PROOF_MAP.md)

---

## 🧪 AI Evaluation System (what I built as the PM)

> Industry consensus in 2026 (Sequoia AI Ascent; Gartner reporting ~85% of GenAI projects fail on poor data/testing): the bottleneck has shifted from building models to **proving they work**. This harness is that proof. *I defined and owned it as the product manager; implementation is the easy part.*

A **7-piece evaluation pipeline** — the part that separates this from a "demo with vibes." Run `python3 eval_runner.py` to reproduce the headline results below (deterministic, no random seed).

| # | Module | What it proves | Real result |
|---|--------|----------------|-------------|
| 1 | **Loader** | Ground truth is real and bounded | 44 precheck records; 43 valid material-cost rows; 22 contract rows (17 with contract price) |
| 2 | **Predictor** | Pricing logic is explicit & interpretable | Flute-stratified median pricing (auditable by senior workers) |
| 3 | **Metrics** | Quality is measured, not claimed | MAE / MAPE / Bias / R² on every run |
| 4 | **Breakdown** | Aggregate metrics don't hide subset failures | Surfaced **BC flute 49.1% MAPE** (material-cost breakdown, n=9) as a named failure mode with a root-cause hypothesis |
| 5 | **Regression** | "Improvements" don't silently break other things | Caught a real trade-off: MAPE −10.8pp **but** Bias degraded −0.05→−0.20 — flagged before shipping |
| 6 | **ContractEval** | Model is tested against business reality | Contract-price MAPE **41.3% → 14.3%** overall (n=17); **9.9%** on mainstream EB domestic (n=15) — both reproducible via `eval_runner.py` |
| 7 | **DriftMonitor** | Quality is monitored over time | `weekly_eval.py` flags ≥5pp drift; CI-friendly exit codes (0/1/2); JSONL history |

**Three things this proves about how I work:**

- **I measure quality where it's hard.** A `Regression` module that defends *all four* metrics simultaneously is the difference between "MAPE went down, ship it" and "MAPE went down but we're now quietly losing margin on every quote." (See [EVAL_REPORT.md §3](EVAL_REPORT.md).)
- **I do error analysis myself, not delegate it.** The `Breakdown` module isolated BC-flute underestimation; a separate **data-semantic audit** caught that the field I was scoring (`material ¥/m²`) was *not* the customer's contract price — a data-meaning bug that would have invalidated the whole eval. Finding that is PM work.
- **I report honestly.** R² ≈ 0.18 for the interpretable baseline is disclosed, not hidden behind a marketing accuracy claim. All metrics are **conditional on known material area** and do not yet measure end-to-end sizing — stated plainly.

---

## 🎯 The PM Judgment: Why Pricing Does NOT Use an LLM

The most common AI-PM mistake in 2026 is forcing an LLM into a workflow that shouldn't have one. I made the opposite call, on purpose:

- **Pricing is deterministic** because factory contract amounts require an audit trail, reproducibility, and zero hallucination. A senior worker (or an auditor) can trace exactly why a number came out.
- **AI is used only where uncertainty is genuine** — explaining the quote, flagging risky segments (e.g. BC export outliers), detecting missing inputs, and drafting a human-review note.
- **The final price stays rule-and-human-owned.** No black-box model decides money.

> **Interview line:** *"A fresh bootcamp grad bolts an LLM onto everything. A real PM knows when not to. I split the system on purpose — deterministic, auditable pricing; AI as a second pair of eyes for review and explanation. That's a risk-and-governance decision, not a capability gap."*

The AI review layer (a 3-role advisor, below) **now runs on a real model with its own eval** — risk-recall, overreach guards, per-call traces — see the [Multi-Agent Advisor](#multi-agent-advisor-agents--real-llm-review-under-eval) section and [EVAL_REPORT.md §11](EVAL_REPORT.md). It still never sets the price; that boundary is the point.

---

## The 5 Production Checkpoints

Every senior reviewer knows these five words. This project covers them — here's where:

| Checkpoint | Status | Where |
|---|:--:|---|
| **Data** | ✅ | 2,222 legacy `.docx` work orders → `python-docx` extraction → **2,155 anonymized rows** in SQLite; data-semantic audit |
| **Guardrails** | ✅ | Deterministic pricing (not LLM); 4-layer anonymization; public/internal mode that fails closed |
| **Evaluation** | ✅ | The 7-piece harness above |
| **Deploy** | ✅ | Live on Streamlit Cloud (anonymized demo DB) |
| **Monitor** | ✅ | `weekly_eval.py` drift monitor; CI/cron exit codes |
| *Access control* | 🔲 | On roadmap (noted honestly, not claimed) |

---

## The Problem

A traditional packaging factory quotes prices entirely from senior workers' tacit knowledge. The same order quoted by different workers varies significantly — pricing depends on material gauge, machine state, and individual hand-feel, with no documented formula. Quote latency is high (~30 min/order), the know-how is non-transferable, and there is no way to audit or improve pricing systematically.

## The Solution

A digital quotation and quality-control workflow built from **2,155 anonymized historical work orders** and **44 precheck cost records**, wrapped in the reproducible evaluation + monitoring layer above.

- **Current conditional contract-price eval:** MAPE **14.3%** overall (n=17) on the public anonymized fixture; **9.9%** on mainstream EB domestic orders (n=15, one major customer — not yet a cross-customer claim). Both segments reproduce via `eval_runner.py`. Assumes known material area; does not measure sizing accuracy.
- **Path to end-to-end (tacit → explicit):** the material-area input above used to be an approximation. I obtained the actual hand-written cutting-size formula from a senior worker and engineered it into `sizing_engine.py`, so the approximation can be replaced with a real, auditable area calculation. *Status: formula captured ✅; wiring it into the eval and validating it against independent cutting records is on the roadmap — so this README does not yet claim end-to-end accuracy.*
- **Named failure mode:** BC export outliers remain high-error (47.3% MAPE, n=2) — next iteration is product-configuration features, not blind retuning.
- **Latency:** manual quoting ≈ 30 min; the 30-second-workflow claim is pending a timed public-demo run (stated as pending, not done).
- **Procurement extension:** a real woven-bag purchasing case turns contract-tolerance, entity-mismatch, and negotiation risk into AI-assisted review tasks ([docs/PROCUREMENT_CASE_WOVEN_BAG.md](docs/PROCUREMENT_CASE_WOVEN_BAG.md)).

## Architecture

```
2,222 .docx work orders  →  python-docx extraction  →  2,155 anonymized rows  →  SQLite
                                                                                    ↓
                                                                        Feature Engineering
                                                                         (flute type, board
                                                                          weight, lamination,
                                                                          die-cutting, 15+)
                                                                                    ↓
                                                              Deterministic Predictor (rules)
                                                              + experimental GBM baseline (offline)
                                                                                    ↓
                                                                       Streamlit Web UI
                                                              (quote / search / advanced analysis /
                                                               AI advisor / prepress QA)
                                                                                    ↓
                                                              Evaluation Harness (7-piece)
                                                              Loader→Predictor→Metrics→Breakdown
                                                              →Regression→ContractEval→DriftMonitor
```

## Multi-Agent Advisor (`agents/`) — real LLM review, under eval

A **3-role collaboration** (Intelligence → Analysis → Critic) with deliberate engineering trade-offs:

- **3 roles, not 5** — each extra agent multiplies failure surface; 3 is the minimum to show separation of concerns + a quality gate.
- **Heterogeneous degradation** — when a real LLM call fails, it drops to a mock instead of retrying the same provider.
- **Surfaced intermediate artifacts** — the UI shows every agent's output, not just the final answer (debuggable, not black-box).

> **Status (P1 done):** the `Critic` role now runs on a real model (`deepseek-v4-pro`, OpenAI-compatible) **with mock fallback** when no key is present — the public demo never breaks. Its outputs sit under the same eval discipline as the pricing formula: **risk-recall, hallucination/overreach guards, and per-call traces** over 10 human-anchored cases (`llm_eval.py`). Honest part of the story: the *first* real run **failed the overreach gate and produced invalid verdicts** — the eval caught JSON truncation, non-determinism, and a guardrail false-positive. After fixing, the real model's risk-recall (**0.85**) exceeds the if-else mock (0.82), with **overreach 0 / invalid verdicts 0**. See [EVAL_REPORT.md §11](EVAL_REPORT.md). The model never sets price — pricing stays deterministic.

## Quick Start

```bash
git clone https://github.com/wwwaaarrthur/yiwei-cost-engine.git
cd yiwei-cost-engine
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
YIWEI_APP_MODE=public python3 -m streamlit run app.py     # opens http://localhost:8501
python3 eval_runner.py                                     # reproduce the eval numbers above
```

## Data Privacy

- `data/demo.db` is **fully anonymized** — real client/supplier names replaced with role labels (e.g. `大型农化客户A`) via `anonymize.py` (4-layer mapping + `--verify`).
- `public_view.py` adds a UI-level guardrail; production `data/process_sheets.db` is never committed.
- Latest local verification: **0 sensitive-token residue** in `data/demo.db`. Raw evidence, real identities, and UAT notes stay private.

## Roadmap

Done: live Streamlit demo · contract-price eval 41.3%→14.3% (reproducible) · EB domestic 9.9% · employee-confirmed sizing engine · regression + drift monitors · GBM baseline experiment (R² 0.20→0.63, offline) · prepress proof verifier · **real DeepSeek Critic + LLM-output eval (risk-recall 0.85, overreach 0)**.

Highest-ROI next:

- [x] **P1 — `Critic` advisor real on `deepseek-v4-pro` + dedicated LLM-output eval** ✅ (risk-recall 0.85 > mock 0.82, overreach 0, invalid 0, per-call traces; the eval caught 3 real integration bugs on first run — see [EVAL_REPORT.md §11](EVAL_REPORT.md)). Next: an LLM-judge validated against the human anchors (TPR/TNR) to replace string-match recall.
- [ ] **Wire the frontline cutting-size formula into the eval.** The senior-worker formula is captured in `sizing_engine.py` ✅; next: replace the known-area approximation in `eval_runner.py`, validate the formula against independent cutting records (accuracy, not just formula-alignment), then report end-to-end quote accuracy instead of the area-conditional 14.3%.
- [ ] Add product-configuration features for BC export outliers.
- [ ] Time one live quote flow to verify/qualify the 30min→30s latency claim.
- [ ] Add one anonymized UAT / stakeholder-feedback artifact.

UAT/adoption boundary: prepared templates and demo availability are not UAT passed, user sign-off, or sustained adoption. Those claims stay pending until real business-user evidence exists.

> On GBM: a gradient-boosted baseline reaches R² 0.63 offline, but it is **deliberately not shipped** into pricing at n=45 — productionizing a model on that little data would be a judgment failure, not a feature. It stays an evaluated experiment until data and business risk justify it.

## Background

Built as an AI Product Manager / Digital Transformation portfolio project — the flagship case for "AI deployment in traditional manufacturing": operations workflow redesign, ML evaluation, privacy-safe deployment, and the product judgment of where AI does and does not belong.

> "I don't replace the senior workers. I turn their tacit knowledge into a verifiable, transferable, audited system."
