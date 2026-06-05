# Yiwei Public Release Policy

This project uses a layered public-release model: show product capability, hide factory-sensitive details.

## Release Layers

| Layer | Audience | Public? | Content |
|---|---|---:|---|
| Portfolio entry page | Recruiters, interviewers, search engines | Yes | Problem, workflow, evidence, caveats, links |
| Streamlit demo | Recruiters, interviewers | Yes | Anonymized workflow demo, aggregate metrics, no internal DB |
| GitHub repository | Technical reviewers | Yes | App code, tests, docs, anonymization tooling, derived demo fixtures |
| Private evidence pack | Interview discussion only | No | Raw work orders, real customer names, internal prices, staff feedback, UAT notes |

## Public Demo Rules

- `YIWEI_APP_MODE=public` must be used for Streamlit Cloud.
- Public mode must load `data/demo.db`, never `data/process_sheets.db`.
- Public mode generalizes customer/product/material/file/note display fields.
- Public mode hides row-level cost, contract-price, supplier-price, and full CSV export.
- Public mode can show aggregate accuracy, normalized indices, sample counts, workflow tabs, and caveats.
- Real LLM calls stay off by default; public demo should work in mock mode with no secrets.

## Private Data Rules

The following must not be published:

- Raw `.docx`, `.xlsx`, image, or PDF source files from factory work.
- Real customer, supplier, brand, staff, phone, address, or contact details.
- `data/process_sheets.db`, `anonymize_mapping.json`, Streamlit secrets, API keys.
- Screenshots from internal mode unless manually reviewed and redacted.
- Claims such as `UAT passed`, `adoption achieved`, or quantified labor savings without evidence.

## Interview Framing

Use this sentence:

> I made the portfolio version public with anonymized demo data, while keeping business-sensitive order details private. This shows both product delivery and responsible AI/data governance.

Chinese version:

> 我公开的是产品能力，不公开企业机密。

## Pre-Publish Checklist

- [ ] Streamlit Cloud environment has `YIWEI_APP_MODE=public`.
- [ ] Streamlit app sharing is set to `This app is public and searchable`.
- [ ] Open the demo in incognito and confirm no login redirect.
- [ ] Confirm sidebar says `PUBLIC DEMO`.
- [ ] Confirm row-level cost and contract-price tables are hidden.
- [ ] Confirm full CSV export is disabled in public mode.
- [ ] Confirm `data/process_sheets.db`, `.streamlit/secrets.toml`, and `anonymize_mapping.json` are absent from git.
- [ ] Confirm README caveats match the live demo claims.
