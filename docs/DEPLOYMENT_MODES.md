# Yiwei Deployment Modes

The app has two intended versions:

| Mode | Audience | Data | How to start |
|---|---|---|---|
| `public` | recruiters, GitHub viewers, Streamlit Cloud | `data/demo.db` only; anonymized | `YIWEI_APP_MODE=public streamlit run app.py` |
| `internal` | factory staff | real `process_sheets.db`; never commit | `YIWEI_APP_MODE=internal YIWEI_DB_PATH=/private/path/process_sheets.db streamlit run app.py` |
| `auto` | local development | `YIWEI_DB_PATH` → `data/process_sheets.db` → `data/demo.db` | `streamlit run app.py` |

## Recommended Setup

Public portfolio:

```bash
YIWEI_APP_MODE=public streamlit run app.py
```

Internal factory lookup:

```bash
YIWEI_APP_MODE=internal YIWEI_DB_PATH=/private/path/process_sheets.db streamlit run app.py
```

Then let staff open the LAN URL, for example:

```text
http://192.168.x.x:8501
```

## Safety Rules

- Public mode is forced to `data/demo.db`.
- Public mode applies `public_view.py` display sanitization for product, material, file, path, and note fields.
- Public mode hides row-level cost / contract-price tables and disables full CSV export.
- Internal mode fails closed if the real DB is missing.
- `data/process_sheets.db` stays gitignored.
- Streamlit Community Cloud should not host real customer data.
- If external access is needed, put the internal app behind VPN or Cloudflare Access.

## Public Portfolio Pattern

Use three layers:

1. Cloudflare Pages static entry page: public, searchable, recruiter-friendly.
2. Streamlit app: public but anonymized, launched with `YIWEI_APP_MODE=public`.
3. Private evidence pack: raw source files, real identities, UAT notes, and internal pricing never go online.

Before publishing, run through [`PUBLIC_RELEASE_POLICY.md`](PUBLIC_RELEASE_POLICY.md).
