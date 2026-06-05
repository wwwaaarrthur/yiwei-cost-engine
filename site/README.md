# Yiwei Cost Engine Static Entry Page

This folder is a static SEO-friendly entry page for Cloudflare Pages.

## Why it exists

The Streamlit app is the working demo, but Streamlit pages are weak as search-entry pages and can be blocked if sharing is private. This static page gives recruiters and search engines a stable public URL, then links to the Streamlit demo and GitHub repo.

The release model is documented in [`../docs/PUBLIC_RELEASE_POLICY.md`](../docs/PUBLIC_RELEASE_POLICY.md): public entry page, public anonymized demo, reviewable code, private raw evidence pack.

## Cloudflare Pages settings

Use these project settings:

| Field | Value |
|---|---|
| Framework preset | None |
| Build command | Leave blank |
| Build output directory | `site` |
| Root directory | Repository root |

After deployment, replace `https://yiwei-cost-engine.pages.dev/` in `index.html`, `robots.txt`, and `sitemap.xml` with the final Cloudflare Pages URL or custom domain.

## Required Streamlit setting

In Streamlit Community Cloud, set the app sharing mode to public:

```text
App settings -> Sharing -> This app is public and searchable
```

Then test the Streamlit URL in an incognito browser before adding it to a resume.

Before switching Streamlit public, confirm:

- `YIWEI_APP_MODE=public` is configured.
- Sidebar shows `PUBLIC DEMO`.
- Row-level cost and contract-price tables are hidden.
- Full CSV export is disabled.
