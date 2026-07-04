# BC Export Error Analysis

## Phenomenon

BC export remains the clearest known high-error segment: BC export conditional MAPE is 47.3% with n=2 in the current Phase D1 segment table (source: `EVAL_REPORT.md:203-209`). This is a known-area price-model limitation, not an end-to-end sizing result (source: `EVAL_REPORT.md:9-13`).

The earlier material-cost breakdown also showed BC flute as a systematic weak spot: BC n=9, base price 2.00 ¥/m², actual median 2.86 ¥/m², MAE 1.517, MAPE 49.1%, Bias -0.928 (source: `EVAL_REPORT.md:36-47`).

## Decomposition

- **Small segment size**: the BC export segment has n=2 in the contract-price eval (source: `EVAL_REPORT.md:207-208`). A two-row segment is enough to name the risk, not enough to tune a new model safely.
- **Ground-truth scope**: Phase C introduced 9 anonymized precheck spreadsheets with 22 rows, and 17 rows have contract price (source: `EVAL_REPORT.md:148-168`). This is valuable but still bounded evidence.
- **Customer concentration**: EB domestic is n=15 from one major customer, so its 9.9% result should not be generalized across all customers (source: `docs/NORTH_STAR_PROOF_MAP.md:40`).
- **Pricing mechanism assumption**: the 14.3% overall result assumes material area is already provided; it does not validate forming, imposition, or the sizing engine end to end (source: `EVAL_REPORT.md:9-13`).
- **Missing product-configuration features**: the remaining BC issue is tied to 4L special configuration such as high-burst paper, coating, and export premium; the documented next fix is product-configuration features, not broad retuning (source: `EVAL_REPORT.md:222-231`).

## Why Not Fix It Now

The honest choice is to keep BC export as a named failure mode until the right data exists. Retuning on n=2 could improve a metric by accident while damaging the mainstream segment. The system already records why this matters: single-metric wins can hide margin risk, and regression checks must defend more than MAPE alone (source: `EVAL_REPORT.md:61-87`).

Current recommended position:

> "BC export is the segment I would not overclaim. The eval surfaced it, explained the likely product-configuration cause, and gives the next data requirement. That is better evidence of product judgment than pretending the outlier is solved."

## Boundary Conditions For Future Iteration

Iterate only when these are available:

1. More BC export examples beyond the current n=2 segment (source: `EVAL_REPORT.md:207-208`).
2. Structured product-configuration fields for high-burst paper, coating/lamination, and export premium (source: `EVAL_REPORT.md:222-231`).
3. Separate checks that protect EB domestic n=15 performance at 9.9% MAPE while testing BC changes (source: `EVAL_REPORT.md:207-209`).
4. A regression report showing MAPE, Bias, and segment breakdown together, not one headline metric (source: `EVAL_REPORT.md:61-87`).
