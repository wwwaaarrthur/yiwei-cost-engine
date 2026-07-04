# Human Anchor Annotation Guide

> Scope: this is a calibration package for Yi to label critic-output agreement. It is not UAT, adoption evidence, or external accuracy proof.

## Source Boundary

- Source file: `data/llm_eval_cases.json`.
- Available source cases: 10 cases, not 40 (source: `EVAL_REPORT.md:362`, `docs/plans/2026-06-07-llm-eval-p1.md:25`).
- Current anchor file: `eval/human_anchor/anchor_set_40.csv`.
- Rows currently populated: 10 actual source cases.
- Missing to requested target: 30 additional real LLM eval cases must be authored before this can be a true 40-case anchor set.

## Columns

| Column | Who fills | Meaning |
|---|---|---|
| `case_id` | Generated | Stable case ID from the existing LLM eval fixture. |
| `input_summary` | Generated | Query, sample context, price range, draft price, and warning summary. |
| `critic_verdict` | Generated | Current mock Critic output: `approve`, `revise`, or `reject`. |
| `critic_reason_summary` | Generated | Short reason or user-facing critic message. |
| `yi_verdict` | Yi only | Yi's label: `approve`, `revise`, or `reject`. Leave blank until Yi labels it. |
| `yi_note` | Yi only | Optional short note explaining boundary cases or disagreement. |

## Label Options

- `approve`: the critic's draft is acceptable with ordinary caveats.
- `revise`: the draft has missing context, weak reasoning, risky phrasing, or needs human review before use.
- `reject`: the draft should not be used because it lacks enough data, crosses a governance boundary, or would mislead a user.

## Boundary Rules

- If the critic suggests a price but keeps the final decision with the human, label based on quality and risk coverage, not on the mere presence of a price.
- If the case has low sample size, BC export risk, missing lamination, or no matching data, expect at least `revise` unless the critic clearly blocks the unsafe claim.
- If `revise` vs `reject` is ambiguous, use `yi_note` to explain the judgment. These disagreements are useful; do not smooth them away.
- Do not fill labels from memory, from Codex, or from a synthetic answer. Yi labels only.

## Time Estimate

- Full requested 40-row set after 30 more real cases exist: about 2-3 hours, per the task brief.

## Compute Agreement

After Yi fills `yi_verdict`, run:

```bash
python3 scripts/compute_anchor_agreement.py eval/human_anchor/anchor_set_40.csv
```

The output includes:

- labeled row count
- agreement rate
- Cohen's kappa
- disagreement case list

If `yi_verdict` is blank, the script correctly reports `pending-labels`.
