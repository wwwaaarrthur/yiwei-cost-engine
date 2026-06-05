# Procurement Case: Woven Bag Purchase Review

Last audited: 2026-05-24

This is an anonymized procurement submodule case for the Yiwei Cost Engine portfolio. It should be presented as part of the same manufacturing digital transformation story, not as a separate flagship project.

## Business Context

The factory needed to purchase a first batch of laminated woven bags. The business risk was not only price; it also included contract tolerance wording, supplier-entity consistency, quality acceptance, and negotiation traceability.

| Field | Anonymized value |
|---|---:|
| Product | Laminated woven bag with inner PE liner |
| Quantity | 30,000 units |
| Final unit price | CNY 1.47 / unit |
| Baseline reference | CNY 1.73 / unit |
| First-order value | CNY 44,100 |
| Estimated unit-price reduction | about 15% |

## Four AI-Assisted Review Opportunities

| Signal | Manual risk | AI-assisted workflow |
|---|---|---|
| Vague tolerance clause | A clause allowed quantity settlement with ±5% ambiguity, which could legitimize under-delivery | Flag vague tolerance, quantify exposure, propose rewritten clause |
| Tolerance misrepresentation | Supplier described tolerance as `±3g per bag`, while the relevant standard should be interpreted through material/area and batch context | Convert supplier wording into comparable percentage range and generate negotiation language |
| Entity mismatch | Chat entity and contract entity differed before manual clarification | Detect mismatch, require business-registration verification, downgrade risk only after evidence |
| Negotiation anomaly | Message withdrawal and wording shift around tolerance terms | Mark as medium-risk negotiation signal and recommend screenshot retention |

## Product Interpretation

This case shows why the project is more than a quote calculator:

- The cost engine answers: **What should this order cost?**
- The procurement module answers: **What hidden risk can make the quoted cost unreliable?**
- The prepress verifier answers: **How do we prevent a correct quote from becoming a production loss?**

Together, they form an operations control loop:

```text
Quote → Contract Review → Supplier Risk → Production Proof → Eval / Drift Monitor
```

## PM Judgment

The key decision was not to force a contract rewrite for every risk. For a first order, the quantified exposure was limited relative to the relationship value and delivery schedule. The chosen control was operational:

- retain key chat evidence,
- require sample acceptance before final payment,
- record weight checks,
- keep the tolerance issue as a renewal negotiation point.

This is the interview-worthy lesson: **AI can surface risk, but the product owner still chooses the business control.**

## Interview Soundbite

> The quoting system tells us whether a price is reasonable. The procurement case taught me that reasonable price is not enough; if the contract tolerance, supplier entity, or proofing process is weak, the margin can still disappear. So I extended the same eval mindset from pricing into procurement risk and production quality gates.

## What Not To Overclaim

- Do not say the procurement module is fully autonomous.
- Do not say every supplier-risk module is productionized unless it is visible in the app.
- Do not present this as a legal review system. Present it as AI-assisted procurement operations risk triage.
