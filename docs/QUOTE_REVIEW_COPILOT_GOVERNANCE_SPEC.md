# Quote Review Copilot — Governance & Eval Boundary Spec

> Version 1.0 · 2026-06-10 · Author: Yi（decisions）/ Claude Code（drafting）
> Type: governance design document. Not an implementation task, not a UAT/adoption claim.
> Architecture principle: **规则算价，AI 审查，人来签字。** (Rule engine prices; AI reviews; human signs.)

## 1. AI Allowed Tasks

The AI review layer (critic agent) may only:

1. Explain quotation composition in business language (which formula inputs drove the price).
2. Flag abnormal or high-risk orders (outlier dimensions, unusual material cost, margin anomalies).
3. Check missing information before a quote goes out (incomplete specs, absent reference orders).
4. Suggest review questions / focus points for the human owner.
5. Retrieve similar historical orders as reference context.

Pricing computation itself belongs exclusively to the deterministic rule engine
(auditable formulas + historical data). The AI never generates, adjusts, or
overrides a price.

## 2. AI Forbidden Tasks

1. Set, modify, or override any price produced by the rule engine.
2. Approve a quotation or trigger sending it to a customer.
3. Issue decisive conclusions ("approve this", "this price is final") — measured as `overreach`, gate = 0.
4. Carry customer-identifying information in any prompt sent to an external model API.
5. Claim UAT passed or adoption achieved (evidence boundary lives in claims, not in code).

## 3. Human Sign-off Point

- Every quotation is reviewed and confirmed by the **salesperson (业务员)** after the
  rule engine computes the price and the AI review layer attaches its findings.
- Sign-off happens **before the quote reaches the customer** — the AI's output is an
  input to the human decision, never a bypass of it.
- Escalation: current single-tier sign-off reflects the actual factory workflow
  (small-team operation). If order value / anomaly tiers are introduced later,
  risk-based escalation (e.g. owner countersign above a threshold) extends this
  section; not claimed as implemented today.

## 4. Data Boundary (three-layer minimum-necessary)

| Layer | Data policy | Rationale |
|---|---|---|
| Internal system queries | Salespeople query by real customer name | Authorized users, legitimate business purpose — inside permission boundary |
| Prompts to external LLM API | Customer identifiers redacted / tokenized; only carton specs, dimensions, material prices, quote composition passed | Data leaves the domain here — this is the actual AI data-boundary control point |
| Public demo site | Fully anonymized | Real customer data on a public site is a compliance incident, not a cosmetic choice |

Minimum-necessary means each layer receives only what its function requires —
not "redact everything", but "no layer sees more than it needs".

## 5. Failure States

- If the AI review layer fails (timeout, malformed output, API error):
  1. Degrade gracefully to rule-engine output + similar-order retrieval (deterministic capabilities remain fully functional).
  2. Tell the user honestly that AI review is unavailable — never fake a review.
  3. Log the failure (type, case context) — failure logs feed the next eval round.

## 6. Eval Metrics (real-run results, deepseek-v4-pro, 2026-06-08, commit 75ba282)

| Metric | Meaning | Result | Gate type |
|---|---|---|---|
| overreach | AI issues forbidden pricing/approval conclusions | **0** | Compliance hard gate — must stay 0 |
| risk-recall | Of truly risky cases, share flagged by AI | **0.85** (real run; mock baseline 0.82) | Quality target — improve continuously |
| missing-info recall | Flags incomplete quote context | 0.80 | Quality target |
| verdict accuracy | Agreement with human-anchor labels | 0.70 | Tracked; misses are revise/reject boundary disagreements, not hallucinations |
| invalid output | Unparseable AI responses | 0 | Hard gate |

Why one gate is 0 and another is not: forbidden actions are a compliance question
(one strike fails), detection quality is an improvement question. The 15% of risky
cases the AI misses **is the quantified justification for the human sign-off step** —
eval numbers and governance design prove each other.

Known limitation: risk-recall currently uses string-match scoring; next step is
LLM-judge validated against human anchors (TPR/TNR) before any metric upgrade claim.

## 7. Claim Boundary

- Current claimable state: working demo + **real-model eval completed** (deepseek-v4-pro, metrics above).
- Not claimable: UAT passed, business adoption, production reliability.
- This line is dynamic — it updates with the evidence ledger, never ahead of it.
  Framework rule: demo proves "it runs", UAT proves "users verified it", adoption
  proves "it is used sustainably". The three are never conflated.

## 30-Second Project Defense (interview asset)

> 价格由规则引擎按公式计算，AI 一概不碰定价。AI 审查层只做四件事：解释报价构成、识别异常订单、检查缺失信息、给复核建议。每张报价单发出前由业务员确认，责任在人。我们用 eval 管 AI：overreach=0 是合规硬门槛；risk-recall 0.85——真有问题的单子 AI 标出 85%，剩下 15% 正是人工审核存在的理由。真实模型还反超了 mock baseline，eval 当场抓出 3 个真 bug——AI 提效，人兜底，互为证据。
