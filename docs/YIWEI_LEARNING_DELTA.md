# Yiwei Learning Delta

Last audited: 2026-05-24

You do not need to relearn the whole Yiwei project after optimization. You only need to learn the delta: what changed, which metrics are safe to say, and how to explain the system in business language.

## What To Relearn

Time budget: 60-90 minutes total.

| Block | Time | Goal |
|---|---:|---|
| Proof map | 15 min | Know which artifact proves which interview claim |
| Metric semantics | 20 min | Separate contract MAPE, material-cost MAPE, R², Bias, and historical `±8%` |
| Demo route | 15 min | Open website, show quote tab, eval report, drift monitor, prepress tab |
| Procurement submodule | 15 min | Explain woven-bag case as cost protection, not a second project |
| Mock answer | 15-25 min | Give a 3-minute answer and survive 5 follow-up questions |

## What Not To Relearn

- Do not memorize every Streamlit tab.
- Do not memorize every formula parameter.
- Do not memorize all procurement case details.
- Do not relearn the code line by line.
- Do not chase new OPC-agent features before the Yiwei story is fluent.

## Three-Minute Interview Story

```text
Yiwei was a traditional packaging manufacturing workflow where pricing depended heavily on senior workers' tacit knowledge. The first problem was not model sophistication; it was that five years of work orders were trapped in irregular documents and could not be searched, evaluated, or improved systematically.

I helped turn 2,222 legacy work-order files into 2,155 anonymized structured rows, then built a Streamlit quotation system and an evaluation pipeline around it. The important part is the eval layer: it tracks MAE, MAPE, Bias, R², segment breakdown, and regression changes, so I can see not only whether accuracy improves, but also whether the model starts systematically underquoting and risking margin.

The current conditional contract-price eval reaches 15.1% MAPE overall on the public anonymized fixture, with the mainstream EB domestic segment at 9.9%. It assumes material area is already known and does not measure sizing accuracy. The system also exposes the weak area honestly: BC export outliers still have high error, so the next iteration is product-configuration features rather than blind retuning.

The broader transformation is that the same operating logic expanded from quotation into procurement and prepress quality checks. For procurement, I used a real woven-bag purchase case to identify contract tolerance risk, supplier-entity mismatch, and negotiation signals. For prepress, the website includes a quality-gate tab that compares customer source materials with designer proof outputs before production.

So my takeaway is: AI in traditional operations is not just about building a model. It is about building a measurable, auditable workflow where humans can trust, review, and improve the system over time.
```

## Five Follow-Up Questions To Practice

1. Why did you use MAPE, Bias, and R² together instead of one accuracy metric?
2. What does it mean that MAPE improved but Bias degraded?
3. Why is EB domestic stronger than BC export in your current system?
4. How did you prevent sensitive customer or supplier data from leaking into GitHub?
5. How would you turn this from a demo into an adopted workflow inside the factory?

## Memory Anchor

Metric wording:

> MAPE tells how far off. Bias tells which direction. R² tells whether the model learned structure. Drift tells whether yesterday's truth still holds today.

Project wording:

> Do not sell "AI magic." Sell a workflow that can be measured, audited, and improved.
