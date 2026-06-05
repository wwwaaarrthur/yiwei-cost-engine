# Yiwei Cost Engine

> **AI-powered cost estimation system for corrugated box manufacturing.**
> End-to-end digital operations case: legacy work-order extraction → cost model → evaluation harness → drift monitor → Streamlit operating app.

[![Built with Streamlit](https://img.shields.io/badge/Built%20with-Streamlit-FF4B4B?logo=streamlit)](https://streamlit.io)
[![Python 3.14](https://img.shields.io/badge/Python-3.14-blue?logo=python)](https://www.python.org)
[![SQLite](https://img.shields.io/badge/Storage-SQLite-003B57?logo=sqlite)](https://sqlite.org)

[**🚀 Live Demo · yiwei-cost-engine.streamlit.app**](https://yiwei-cost-engine.streamlit.app)

> Streamlit Cloud may show a sleep screen on first open. Click "wake up" and wait about 30-60 seconds. If it redirects to a Streamlit login page, the app sharing setting must be changed to **public and searchable**.

For a search-friendly portfolio landing page, see [`site/`](site/). It is designed for Cloudflare Pages and links to the Streamlit demo.

Public-release policy: see [`docs/PUBLIC_RELEASE_POLICY.md`](docs/PUBLIC_RELEASE_POLICY.md). The intended model is a public portfolio entry page + public anonymized Streamlit demo + private raw evidence pack.

---

## For Recruiters / Interviewers

Start here if you have 5 minutes:

1. Open the [live demo](https://yiwei-cost-engine.streamlit.app) and try the **首页报价** tab.
2. Read [EVAL_REPORT.md](EVAL_REPORT.md) §7-9 for the current business-facing evaluation results.
3. Read [docs/NORTH_STAR_PROOF_MAP.md](docs/NORTH_STAR_PROOF_MAP.md) for the interview evidence map.
4. Read [docs/PROCUREMENT_CASE_WOVEN_BAG.md](docs/PROCUREMENT_CASE_WOVEN_BAG.md) for the procurement risk case.

The project is designed to demonstrate **Digital Transformation / AI Product Management judgment**, not just model training.

## The Problem

A traditional packaging factory quotes prices entirely from senior workers' tacit knowledge. The same order quoted by different workers shows significant variance because pricing depends on material gauge variation, machine state, and individual hand-feel — there is no documented formula. Quote latency is high (~30 minutes per order), the know-how is non-transferable, and there is no way to audit or improve pricing decisions systematically.

## The Solution

A digital quotation and quality-control workflow built from **2,155 anonymized historical work orders** and **44 precheck cost records**, wrapped in a reproducible evaluation and monitoring layer.

- **Quote latency**: manual quoting is roughly 30 minutes; the 30-second workflow claim is pending a timed public-demo run
- **Current conditional contract-price eval**: MAPE **15.1%** overall on the public anonymized fixture; it assumes precheck material area is already known and does not measure sizing accuracy. Mainstream EB domestic orders are **9.9%** on n=15 rows from one major customer, not yet a cross-customer generalization claim
- **Monitoring**: `weekly_eval.py` detects ≥5pp metric drift and exits non-zero for CI/cron use
- **Failure mode surfaced**: BC export outliers remain high-error (MAPE 48.9%) — the next iteration is product-configuration features, not blind retuning
- **Procurement extension**: a real woven-bag purchasing case turns contract tolerance, entity mismatch, and negotiation risk into AI-assisted review tasks

> The point is not to claim a specific accuracy number — it is to build the **eval scaffolding** that makes model iteration safe, auditable, and decision-grounded. Honest measurement and trade-off articulation matter more than headline metrics.

## What's Inside

| Component | What it demonstrates |
|---|---|
| **7-piece eval system** (`eval_runner.py`, `weekly_eval.py`) | Loader / Predictor / Metrics / Breakdown / Regression / ContractEval / DriftMonitor. See [EVAL_REPORT.md](EVAL_REPORT.md). |
| **Multi-Agent advisor** (`agents/`) | 3-role collaboration (Intelligence → Analysis → Critic) with mock-first design and graceful LLM degradation. See [agents/README.md](agents/README.md). |
| **Privacy-by-design anonymization** (`anonymize.py`) | 4-layer mapping (CLIENT / SUPPLIER / BRAND / SENSITIVE_TOKENS) + `--verify` subcommand + JSON mapping isolation (gitignored). |
| **Public demo guardrail** (`public_view.py`) | Generalizes public-mode customer/product/material/file/note display fields and hides row-level cost export. |
| **Streamlit operating app** (`app.py`) | 5 tabs: quote, order search, advanced analysis, AI advisor, and prepress proof verification. |
| **Employee-confirmed sizing engine** (`sizing_engine.py`) | Separates forming mode, face-paper imposition, corrugated imposition, piece counts, and per-carton material area. |
| **Procurement case study** (`docs/PROCUREMENT_CASE_WOVEN_BAG.md`) | Shows how the same system thinking protects cost before and after quotation. |

## Architecture

```
2,222 .docx work orders  →  python-docx extraction  →  2,155 anonymized rows  →  SQLite
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
                                                                       (5 workflow tabs:
                                                                        quote / search /
                                                                        advanced analysis /
                                                                        AI advisor /
                                                                        prepress QA)
                                                                                    ↓
                                                                       Evaluation Harness
                                                                       (eval_runner.py:
                                                                        Loader → Predictor
                                                                        → Metrics →
                                                                        Breakdown →
                                                                        Regression →
                                                                        ContractEval →
                                                                        DriftMonitor)
```

## Quick Start

```bash
git clone https://github.com/wwwaaarrthur/yiwei-cost-engine.git
cd yiwei-cost-engine
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
YIWEI_APP_MODE=public python3 -m streamlit run app.py
```

Open `http://localhost:8501`. The bundled `data/demo.db` (anonymized) loads automatically.

For factory staff, run the internal version with a real database outside git:

```bash
YIWEI_APP_MODE=internal YIWEI_DB_PATH=/private/path/process_sheets.db python3 -m streamlit run app.py
```

See [`docs/DEPLOYMENT_MODES.md`](docs/DEPLOYMENT_MODES.md) for the public/internal/auto mode contract.

## Evaluation Harness (`eval_runner.py`)

A seven-piece evaluation system — the part that separates this from a "demo with vibes":

| Module | Purpose |
|--------|---------|
| **Loader** | Loads 44 precheck records; 43 valid material-cost rows currently enter the early eval |
| **Predictor** | Runs flute-stratified median pricing logic |
| **Metrics** | Computes MAE / MAPE / Bias / R² |
| **Breakdown** | Stratifies error by flute type (BC vs EB) to surface root causes |
| **Regression** | Compares before/after parameter changes — guards against "MAPE improves while Bias quietly deteriorates" (see [EVAL_REPORT.md §3](EVAL_REPORT.md) for a real captured trade-off) |
| **ContractEval** | Evaluates the business-facing quote formula against 22 anonymized spreadsheet rows |
| **DriftMonitor** | Runs weekly metric comparison and flags ≥5pp drift |

Current safe headline: **conditional contract-price MAPE 15.1% overall / 9.9% on EB domestic mainstream orders from n=15 rows for one major customer**. These metrics assume provided material area and do not measure end-to-end sizing accuracy. The earlier 39% → 28.2% result is retained as the material-cost baseline history, not the main business claim.

## Tech Stack

- **Frontend**: Streamlit + Plotly (interactive dashboards)
- **Backend**: Python 3.14, Pandas, SQLite
- **Data extraction**: python-docx (parsing irregular legacy `.docx` work orders)
- **Evaluation**: Custom eval harness (`eval_runner.py`) with contract-price eval
- **Monitoring**: JSONL eval history + CI/cron-friendly drift exit codes (`weekly_eval.py`)

## Project Structure

```
yiwei-cost-engine/
├── app.py                  # Streamlit application (5 workflow tabs)
├── sizing_engine.py        # Employee-confirmed forming/imposition/material-area rules
├── db_config.py            # public/internal/auto database mode resolver
├── eval_runner.py          # Evaluation harness (material-cost + contract-price eval)
├── weekly_eval.py          # Drift monitor (JSONL history + CI-friendly exit codes)
├── train_gbm.py            # Experimental GBM baseline (R² 0.20 → 0.63)
├── extract_data.py         # .docx → SQLite pipeline (v1)
├── extract_data_v2.py      # .docx → SQLite pipeline (v2, cell-position parser)
├── anonymize.py            # Production DB → anonymized demo DB
├── requirements.txt        # Pinned dependencies for Streamlit Cloud
├── EVAL_REPORT.md          # Real eval results + failure analysis
├── DEPLOY.md               # Streamlit Cloud deployment guide
├── docs/
│   ├── NORTH_STAR_PROOF_MAP.md
│   ├── CARTON_SIZING_KNOWLEDGE_BASE.md
│   ├── DEPLOYMENT_MODES.md
│   ├── PROCUREMENT_CASE_WOVEN_BAG.md
│   └── YIWEI_LEARNING_DELTA.md
├── data/
│   ├── demo.db             # Anonymized demo (2,155 work orders + 44 precheck records)
│   ├── ground_truth_22rows.csv
│   └── prepress_reports/
├── tests/
│   ├── test_sizing_engine.py
│   └── test_eval_runner.py
└── README.md
```

## Data Privacy

- `data/demo.db` is **fully anonymized** — real client and supplier names are replaced via `anonymize.py` with role-based labels (e.g. `大型农化客户A`)
- `public_view.py` adds a second UI-level guardrail: public mode generalizes visible product/material/file/note fields and hides row-level cost/contract tables plus full CSV export
- Production `data/process_sheets.db` is **never committed** (excluded in `.gitignore`)
- `YIWEI_APP_MODE=public` forces the demo DB; `YIWEI_APP_MODE=internal` fails closed if a real DB is missing
- Latest local anonymization verification: `0 sensitive token residue` in `data/demo.db`
- Raw evidence, real customer identities, staff feedback, and UAT notes stay private; see [`docs/PUBLIC_RELEASE_POLICY.md`](docs/PUBLIC_RELEASE_POLICY.md)

## Roadmap

Done:

- [x] Streamlit Cloud public demo
- [x] Contract-price eval: 41.3% → 15.1% MAPE on the public anonymized fixture
- [x] Mainstream EB domestic segment: 9.9% MAPE
- [x] Employee-confirmed sizing engine: separate forming / face imposition / corrugated imposition
- [x] Regression tests for `YW26-06-01`, `YW26-06-02`, and a historical double-pairing case
- [x] `weekly_eval.py` drift monitor
- [x] GBM baseline experiment: R² 0.20 → 0.63
- [x] Prepress proof verifier tab

Highest-ROI next steps:

- [ ] Validate corrugated double-pairing direction/reduction with one employee-confirmed work order
- [ ] Build end-to-end sizing accuracy evaluation; current 15.1% MAPE is conditional on known material area
- [ ] Persist order-level standard, compression/stacking requirements, and acceptance-result fields
- [ ] Time one live quote flow to verify or qualify the 30min → 30s latency claim
- [ ] Add one anonymized UAT / stakeholder feedback artifact
- [ ] Add product-configuration features for BC export outliers
- [ ] Merge the procurement case into the app as a visible submodule
- [ ] Add bilingual reviewer summary (English / 中文) after the interview story is fully stable

---

## Background

Built as an AI Product Manager / Digital Transformation portfolio project. Used as the flagship case study for "AI deployment in traditional manufacturing" — the intersection of operations workflow redesign, ML evaluation, privacy-safe deployment, and product judgment.

> "I don't replace the senior workers. I turn their tacit knowledge into a verifiable, transferable system."

For technical details, see [EVAL_REPORT.md](EVAL_REPORT.md) (real eval results, failure analysis, system thinking) and [DEPLOY.md](DEPLOY.md) (Streamlit Cloud deployment guide).
