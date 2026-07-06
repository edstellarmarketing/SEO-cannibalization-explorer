# SEO Cannibalization Explorer

Streamlit app to explore edstellar.com queries where **exactly two pages compete**,
with a slider to filter by how close their average positions are (the position gap).

Data window: 2026-04-05 → 2026-07-03 (Google Search Console). 1,225 two-page conflicts.

## Files
- `app.py` — the Streamlit app
- `cannibalization_data.csv` — the data it reads
- `requirements.txt` — dependencies

## The "🔧 Fix" button — Claude headless CLI (Max/Pro subscription)

Each row has a **Fix** button. Clicking it fetches both competing pages and asks
the **Claude Code headless CLI** (`claude -p`) which sections to change to resolve
the cannibalization. It uses your **Claude Max/Pro subscription**, not an API key.

### One-time auth setup
1. Install Claude Code: https://docs.claude.com/en/docs/claude-code
2. Generate a long-lived subscription token:
   ```bash
   claude setup-token
   ```
   This opens a browser, authenticates against your Max/Pro plan, and prints a
   token starting with `sk-ant-oat...`.
3. Create your env file and paste the token in:
   ```bash
   cp .env.example .env
   # edit .env -> CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat...
   ```
   `.env` is git-ignored, so the token never leaves your machine.

The sidebar shows a green "Authenticated" badge once the token is picked up.

> **Note:** the `claude` CLI must exist on the machine running the app, so the Fix
> button works when you run the app **locally** (or on your own server with Claude
> Code installed). It does **not** work on Streamlit Cloud, which has no CLI.
> Browsing, filtering, and sorting still work fine on Streamlit Cloud.

## Run locally
```bash
pip install -r requirements.txt
cp .env.example .env      # then add your CLAUDE_CODE_OAUTH_TOKEN
streamlit run app.py
```

## Deploy to Streamlit Cloud
1. Push this folder to a GitHub repo:
   ```bash
   git init
   git add .
   git commit -m "SEO cannibalization explorer"
   git branch -M main
   git remote add origin https://github.com/<you>/<repo>.git
   git push -u origin main
   ```
2. Go to https://share.streamlit.io → **New app** → pick the repo/branch → set
   **Main file path** to `app.py` → **Deploy**.

To refresh the data later, regenerate `cannibalization_data.csv`, commit, and push —
Streamlit Cloud redeploys automatically.
