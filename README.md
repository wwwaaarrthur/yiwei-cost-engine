# Yiwei Cost Engine

> **AI-powered cost estimation system for corrugated box manufacturing.**
> Independently built end-to-end: data pipeline → ML feature engineering → evaluation harness → Streamlit web app.

[![Built with Streamlit](https://img.shields.io/badge/Built%20with-Streamlit-FF4B4B?logo=streamlit)](https://streamlit.io)
[![Python 3.14](https://img.shields.io/badge/Python-3.14-blue?logo=python)](https://www.python.org)
[![SQLite](https://img.shields.io/badge/Storage-SQLite-003B57?logo=sqlite)](https://sqlite.org)

[**🚀 Live Demo · yiwei-cost-engine.streamlit.app**](https://yiwei-cost-engine.streamlit.app)

---

## The Problem

A traditional packaging factory quotes prices entirely from senior workers' tacit knowledge. The same order quoted by different workers shows significant variance because pricing depends on material gauge variation, machine state, and individual hand-feel — there is no documented formula. Quote latency is high (~30 minutes per order), the know-how is non-transferable, and there is no way to audit or improve pricing decisions systematically.

## The Solution

A cost-prediction baseline trained on **2,086 historical work orders** (extracted from 2,222 `.docx` files spanning 2021.02 – 2026.02), wrapped in a **5-module evaluation pipeline** that surfaces failure modes and guards against silent regressions.

- **Quote latency**: 30 minutes → 30 seconds
- **Baseline MAPE**: 39% (flute-stratified median pricing — intentionally simple, interpretable starting point)
- **After one round of eval-driven tuning**: MAPE 28.2% (improvement of 10.8 percentage points)
- **Failure mode surfaced**: BC flute systematically underestimated (MAPE 49.1%, Bias -0.928 ¥/m²) — root-cause hypothesis and iteration plan documented in [EVAL_REPORT.md](EVAL_REPORT.md)

> The point is not to claim a specific accuracy number — it is to build the **eval scaffolding** that makes model iteration safe, auditable, and decision-grounded. Honest measurement and trade-off articulation matter more than headline metrics.

## Architecture

```
2,222 .docx work orders  →  python-docx extraction  →  2,086 structured rows  →  SQLite
                                                                                    ↓
                                                                        Feature Engineering
                                                                       (15+ features:
                                                                        flute type, board
                                                                        weight, lamination,
                                                                        die-cutting...)
                                                                                    ↓
                                                                            Predictor
                                                                       (flute-stratified
                                                                        median pricing)
                                                                                    ↓
                                                                       Streamlit Web UI
                                                                       (3 main tabs + 5 sub-tabs:
                                                                        quote / search /
                                                                        advanced analysis
                                                                        [precision · stats ·
                                                                         board calc · price
                                                                         adjust · data browse])
                                                                                    ↓
                                                                       Evaluation Harness
                                                                       (eval_runner.py:
                                                                        Loader → Predictor
                                                                        → Metrics →
                                                                        Breakdown →
                                                                        Regression)
```

## Quick Start

```bash
git clone https://github.com/wwwaaarrthur/yiwei-cost-engine.git
cd yiwei-cost-engine
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 -m streamlit run app.py
```

Open `http://localhost:8501`. The bundled `data/demo.db` (anonymized) loads automatically.

## Evaluation Harness (`eval_runner.py`)

A five-module evaluation pipeline — the part that separates this from a "demo with vibes":

| Module | Purpose |
|--------|---------|
| **Loader** | Loads 43 pre-check orders as ground truth |
| **Predictor** | Runs flute-stratified median pricing logic |
| **Metrics** | Computes MAE / MAPE / Bias / R² |
| **Breakdown** | Stratifies error by flute type (BC vs EB) to surface root causes |
| **Regression** | Compares before/after parameter changes — guards against "MAPE improves while Bias quietly deteriorates" (see [EVAL_REPORT.md §3](EVAL_REPORT.md) for a real captured trade-off) |

**Why this matters:** AI quality assurance is the #1 cited differentiator for AI Product Managers in 2026 (Product School, HBR). This harness is reusable for any prediction system, not just packaging.

## Tech Stack

- **Frontend**: Streamlit + Plotly (interactive dashboards)
- **Backend**: Python 3.14, Pandas, SQLite
- **Data extraction**: python-docx (parsing irregular legacy `.docx` work orders)
- **Evaluation**: Custom 5-module eval harness (`eval_runner.py`)

## Project Structure

```
yiwei-cost-engine/
├── app.py                  # Streamlit application (24KB, 3 main tabs + 5 sub-tabs)
├── eval_runner.py          # Evaluation harness (12KB, 5 modules)
├── extract_data.py         # .docx → SQLite pipeline (v1)
├── extract_data_v2.py      # .docx → SQLite pipeline (v2, cell-position parser)
├── anonymize.py            # Production DB → anonymized demo DB
├── requirements.txt        # Pinned dependencies for Streamlit Cloud
├── EVAL_REPORT.md          # Real eval results (n=43) + failure analysis
├── DEPLOY.md               # Streamlit Cloud deployment guide
├── data/
│   └── demo.db             # Anonymized demo (1MB, 2,086 work orders + 16 precheck costs)
└── README.md
```

## Data Privacy

- `data/demo.db` is **fully anonymized** — real client and supplier names are replaced via `anonymize.py` with role-based labels (e.g. `大型农化客户A`)
- Production `data/process_sheets.db` is **never committed** (excluded in `.gitignore`)

## Roadmap

- [ ] BC-flute sub-model isolation (current largest error source — MAPE 49.1%, Bias -0.928, see [EVAL_REPORT.md §2](EVAL_REPORT.md))
- [ ] XGBoost / LightGBM baseline upgrade (target overall MAPE < 20%)
- [ ] `weekly_eval.py` drift monitor (auto-alerts on >5pp MAPE drift)
- [ ] Streamlit Cloud public demo URL (see [DEPLOY.md](DEPLOY.md))
- [ ] LLM-as-Judge layer for natural-language quote queries
- [ ] Bilingual UI (English / 中文)

---

## Background

Built by a single developer over 4 weeks as part of an AI Product Manager portfolio. Used as the flagship case study for "AI deployment in traditional manufacturing" — the intersection of operations research, ML engineering, and product thinking.

> "I don't replace the senior workers. I turn their tacit knowledge into a verifiable, transferable system."

For technical details, see [EVAL_REPORT.md](EVAL_REPORT.md) (real eval results, failure analysis, system thinking) and [DEPLOY.md](DEPLOY.md) (Streamlit Cloud deployment guide).
