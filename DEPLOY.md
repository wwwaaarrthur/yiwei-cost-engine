# Streamlit Community Cloud Deployment Guide

> 5-step deployment from this repo to a public URL like `yiwei-cost-engine.streamlit.app`.
> Estimated time: 15-30 minutes.

---

## Prerequisites

- ✅ `requirements.txt` — committed and pinned
- ✅ `app.py` — the Streamlit entrypoint
- ✅ `data/demo.db` — anonymized public data, ~1MB (under 100MB limit)
- ✅ `.gitignore` — excludes `.venv/`, `data/process_sheets.db`, `.streamlit/secrets.toml`
- ✅ Public GitHub repo: `https://github.com/wwwaaarrthur/yiwei-cost-engine`

---

## Step 1 · Sign in to Streamlit Community Cloud

1. Open **https://share.streamlit.io/**
2. Click **"Sign in with GitHub"**
3. Authorize Streamlit to access your public repositories (read-only is sufficient for public repos)

---

## Step 2 · Create the App

1. From your workspace, click **"Create app"** (top-right)
2. Choose **"Deploy a public app from GitHub"**
3. Fill in:
   - **Repository**: `wwwaaarrthur/yiwei-cost-engine`
   - **Branch**: `main`
   - **Main file path**: `app.py`
   - **App URL**: `yiwei-cost-engine` (gives you `yiwei-cost-engine.streamlit.app`)

---

## Step 3 · ⚠️ Critical: Set Python Version via Advanced Settings

> The `runtime.txt` file is [known to be ignored](https://discuss.streamlit.io/t/runtime-txt-ignored-streamlit-cloud-always-uses-python-3-13-causing-blis-spacy-build-failures/116972) by Streamlit Community Cloud. You **must** set Python version through the UI.

1. Before clicking "Deploy", click **"Advanced settings"**
2. **Python version**: Select **`3.13`** (recommended — currently the most stable Streamlit Cloud version; works with all dependencies in `requirements.txt`)
   - If `3.14` is offered and you want bleeding edge, it's also supported but less battle-tested
   - Avoid `3.10` — some dependencies may not have pre-built wheels
3. **Secrets**: Leave blank (this project has no secrets)
4. Click **"Save"**

---

## Step 4 · Deploy

1. Click **"Deploy"**
2. Watch the build log (right panel):
   - "Installing dependencies..." (~2-3 minutes for numpy/pandas/plotly)
   - "Starting up Streamlit..." (~30 seconds)
3. If you see **"Your app is live!"** — proceed to Step 5

### If the build fails

Common issues and fixes:

| Error | Fix |
|---|---|
| `python-docx` not found | Check `requirements.txt` has `python-docx==1.2.0` (not `docx`) |
| `data/demo.db` not found | Confirm `data/demo.db` was actually committed (not in `.gitignore`) |
| Python version mismatch | Delete the app, redeploy with different Python version in Advanced settings |
| Module not found | Compare `requirements.txt` to actual `import` statements in `app.py` |
| Resource exhausted | The free tier has 1GB memory limit. Check if any data file is too large. |

---

## Step 5 · Verify and Capture the URL

1. Click the live URL (e.g. `https://yiwei-cost-engine.streamlit.app`)
2. Test the 3 main tabs:
   - 🏠 **首页报价**: Enter sample params, verify a quote comes back
   - 🔍 **订单查找**: Search a sample order
   - ⚙️ **高级分析**: All 5 sub-tabs render
3. Open the app on mobile (Streamlit is responsive) — confirm it works there too

---

## Step 6 · Update Resume + Project README

Once the URL is live:

### Add to `README.md` (top of repo)

```markdown
[![Built with Streamlit](https://img.shields.io/badge/Built%20with-Streamlit-FF4B4B?logo=streamlit)](https://streamlit.io)
[**🚀 Live Demo · yiwei-cost-engine.streamlit.app**](https://yiwei-cost-engine.streamlit.app)
```

### Update Resume `1.4 Projects · Project 1` line

From:
```
独立开发 · 2026.03 – 至今 · [GitHub](https://github.com/wwwaaarrthur/yiwei-cost-engine)
```

To:
```
独立开发 · 2026.03 – 至今 · [GitHub](...) · [Live Demo](https://yiwei-cost-engine.streamlit.app)
```

---

## Operations · After Deployment

### Continuous Deployment

Every time you `git push` to `main`, Streamlit Cloud auto-rebuilds. Expect ~3 minutes from push to live.

### Resource Limits (Free Tier)

| Resource | Limit |
|---|---|
| Apps | Unlimited public apps (per workspace) |
| Memory | 1 GB per app |
| Storage | 50 MB ephemeral |
| Inactivity | App sleeps after 7 days inactive; wakes on first hit (~30s cold start) |

### Wake-on-Demand

If HR clicks your URL after long inactivity, they may see a "Yes, get this app back up!" button — clicking wakes it in ~30s. This is normal. If you want to prevent this for an interview, hit the URL 10 minutes before to warm it up.

### Monitoring

- App logs: visible in the Streamlit Cloud workspace panel
- App analytics: visit count, geographic distribution (also in workspace)

---

## Troubleshooting

### "Module not found" after deploy works locally

Streamlit Cloud uses a clean container — only `requirements.txt` matters. If something imports cleanly locally but fails on Cloud, it means the dependency is in your `.venv` but not pinned in `requirements.txt`.

Fix:
```bash
# Local
.venv/bin/pip freeze | grep -i <missing-package>
# Copy the line into requirements.txt, commit, push
```

### App is slow on first load

Cold start. Streamlit Cloud caches the data after first load. To pre-warm before a demo:
```bash
curl https://yiwei-cost-engine.streamlit.app -s -o /dev/null
```

---

## Reference

- [Streamlit Cloud · Deploy your app](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app)
- [App dependencies](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies)
- [Upgrade Python version](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app/upgrade-python)

---

_Last updated: 2026-05-18_
