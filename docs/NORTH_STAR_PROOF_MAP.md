# Yiwei North Star Proof Map

Last audited: 2026-06-15

Purpose: make the existing Yiwei Cost Engine easier to use as evidence for Hong Kong Digital Transformation / AI Product Manager interviews. This file does not add product scope. It maps the already-built website, GitHub repo, eval outputs, and procurement cases to interview signals.

## Executive Positioning

Yiwei should be presented as a traditional manufacturing digital transformation case, not as a generic AI demo.

Core story:

> I turned an experience-based packaging quotation and procurement workflow into an auditable digital operations system: structured legacy work orders, built pricing and evaluation pipelines, added drift monitoring, and extended the same operating logic to procurement risk and prepress quality checks.

## Evidence Map

| Interview signal | Project evidence | Concrete artifact | Best talking point |
|---|---|---|---|
| Business process transformation | 2,222 legacy work-order files structured into 2,155 anonymized rows | `extract_data.py`, `data/demo.db`, Streamlit app | From tacit worker knowledge to searchable, auditable data |
| AI evaluation discipline | Loader / Predictor / Metrics / Breakdown / Regression eval pipeline | `eval_runner.py`, `EVAL_REPORT.md` | AI quality must be measured, not claimed |
| Metric trade-off judgment | MAPE improved while Bias degraded in regression test | `EVAL_REPORT.md` section 3 | Single-metric wins can hide margin risk |
| Production monitoring mindset | Weekly drift monitor with exit-code semantics | `weekly_eval.py` | Treat AI eval like a scheduled operations control |
| Business-friendly ML | Conditional contract-price MAPE 14.3%; EB domestic mainstream MAPE 9.9% | `eval_runner.py`, `data/ground_truth_22rows.csv` | Keep known-area evaluation scope explicit |
| Tacit-knowledge digitization | Employee-confirmed sizing rules separated from historical inference | `sizing_engine.py`, `tests/test_sizing_engine.py`, `docs/CARTON_SIZING_KNOWLEDGE_BASE.md` | Convert worker experience into versioned rules with explicit human-review boundaries |
| Failure analysis | BC export outlier remains high-error | `EVAL_REPORT.md` sections 7-9 | Honest limitation plus next iteration plan |
| Privacy and deployment hygiene | Production/demo DB separation and anonymization scripts | `anonymize.py`, `anonymize_csv.py`, `.gitignore` | Public portfolio without leaking business data |
| Procurement operations extension | Woven-bag case with risk, tolerance, entity, negotiation signals | `docs/PROCUREMENT_CASE_WOVEN_BAG.md` | AI not only calculates cost; it protects cost |
| Multimodal operations QA | Prepress proof verifier integrated into Tab 5 | `app.py`, `data/prepress_reports/` | AI quality gate before costly production mistakes |

## Metrics To Say Carefully

Use these as the current safe interview numbers:

| Metric | Safe wording |
|---|---|
| 2,155 rows | Anonymized structured work-order rows visible in the public demo |
| 44 precheck records | 43 valid rows enter the early material-cost eval; keep the sample caveat explicit |
| 22-row contract ground truth | Separate contract-price validation source |
| Conditional contract MAPE 14.3% | Current price-model result when material area is already provided; not sizing or end-to-end quote accuracy |
| EB domestic conditional MAPE 9.9% | Mainstream order segment under the same known-area condition; n=15 from one major customer |
| GBM R² 0.20 to 0.63 | Evidence that feature-based ML learns structure, not yet the main production quote claim |
| 30min to 30s | Workflow latency claim; keep as experience estimate unless timed demo evidence is added |

## Claims To Avoid

- Do not say the system is fully autonomous. Say AI-assisted, human-reviewed, auditable workflow.
- Do not merge `±8%` with MAPE. `±8%` is historical business narrative; MAPE is eval terminology.
- Do not describe `14.3%` as end-to-end quote accuracy. The current eval assumes material area is known.
- Do not say the BC export case is solved. It remains the clearest known limitation.
- Do not present procurement-ai as a separate flagship. Treat it as a submodule of the same Yiwei transformation story.
- Do not imply all procurement modules are production code unless their code is merged and demoable.

## Current Audit Result

Local checks run on 2026-06-15:

```text
python3 eval_runner.py
  Conditional contract-price MAPE: 14.3%
  EB domestic conditional MAPE: 9.9%
  BC export conditional MAPE: 47.3%
  Status: usable

python weekly_eval.py --dry-run
  Drift: BC flute drift alert vs 2026-06-05 baseline (53.5% -> 47.3%)
  EB contract MAPE: 9.9%
  BC contract MAPE: 47.3%

python3 -m py_compile app.py eval_runner.py weekly_eval.py llm_eval.py agents/critic_agent.py agents/llm_client.py
  Status: pass
```

## Highest-ROI Remaining Gaps

1. Add one timed demo run to verify or qualify the `30min -> 30s` efficiency claim.
2. Convert the procurement case from document evidence into a visible cost-engine app submodule.
3. Add one non-family stakeholder artifact: UAT note, feedback quote, approval screenshot summary, or anonymized acceptance note.
4. Add a short README section that links to this proof map and tells recruiters what to inspect first.
