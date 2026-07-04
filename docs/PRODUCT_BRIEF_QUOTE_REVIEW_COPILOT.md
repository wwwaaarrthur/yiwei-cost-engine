# [DRAFT — 待 Yi 审] Quote Review Copilot Product Brief

## Problem

Factory quotation work mixes deterministic cost calculation with human judgment: material cost, order quantity, export/domestic assumptions, customer context, and missing information all matter. The risk is not only "wrong price"; it is an unauditable workflow where nobody can explain why a quote is safe to send.

## User

- Primary user: salesperson or operations owner reviewing a carton quotation before it reaches a customer.
- Secondary reviewer: interviewer or recruiter inspecting whether the project has AI governance, not just a demo screen.

## Solution Boundary

The rule engine computes price. The AI review layer explains, flags, asks, and cites; it never sets, modifies, approves, or sends a price (source: `docs/QUOTE_REVIEW_COPILOT_GOVERNANCE_SPEC.md:17-27`).

The current public demo is based on 2,155 anonymized structured work-order rows (source: `docs/NORTH_STAR_PROOF_MAP.md:36`). Current conditional contract-price evaluation is 14.3% MAPE when material area is already known, not end-to-end sizing accuracy (source: `docs/NORTH_STAR_PROOF_MAP.md:39`). EB domestic conditional MAPE is 9.9% on n=15 from one major customer, so it is a segment result, not a cross-customer claim (source: `docs/NORTH_STAR_PROOF_MAP.md:40`).

## Governance Mechanism

- **Citation**: AI review must refer to the same quote inputs, historical-order context, and eval boundaries visible to the user.
- **Fallback**: if the AI review layer fails, the system must degrade to deterministic rule output plus similar-order retrieval and tell the user that AI review is unavailable (source: `docs/QUOTE_REVIEW_COPILOT_GOVERNANCE_SPEC.md:51-56`).
- **Human review**: every quotation is reviewed by the salesperson before it reaches the customer; AI output is input to that decision, not a bypass (source: `docs/QUOTE_REVIEW_COPILOT_GOVERNANCE_SPEC.md:29-38`).
- **Audit trail**: overreach is a hard gate and must remain 0; current governance spec records overreach=0, risk-recall=0.85, missing-info recall=0.80, verdict accuracy=0.70, and invalid output=0 (source: `docs/QUOTE_REVIEW_COPILOT_GOVERNANCE_SPEC.md:58-74`).

## Verifiable Metrics

Use these carefully:

- "2,155 anonymized structured rows are visible in the public demo" (source: `docs/NORTH_STAR_PROOF_MAP.md:36`).
- "Conditional contract-price MAPE is 14.3% when material area is already known; this is not sizing or end-to-end quote accuracy" (source: `docs/NORTH_STAR_PROOF_MAP.md:39`).
- "EB domestic conditional MAPE is 9.9% on n=15 from one major customer" (source: `docs/NORTH_STAR_PROOF_MAP.md:40`).
- "BC export remains the known high-error segment at 47.3% MAPE, so the limitation is named rather than hidden" (source: `EVAL_REPORT.md:207-209`).
- "The 30min-to-30s latency line remains an experience estimate until timed demo evidence exists" (source: `docs/NORTH_STAR_PROOF_MAP.md:42`).

## Known Limitations

- No UAT passed claim and no adoption claim are available today (source: `docs/QUOTE_REVIEW_COPILOT_GOVERNANCE_SPEC.md:76-82`).
- The current LLM review cases are human-anchored, formula-alignment-grade, not external accuracy proof (source: `EVAL_REPORT.md:383-387`).
- BC export outliers need product-configuration features before iteration is justified (source: `EVAL_REPORT.md:226-231`).
- Timed-demo evidence is still pending if `scripts/demo_t01_timer.py` cannot render Streamlit controls in headless mode.
