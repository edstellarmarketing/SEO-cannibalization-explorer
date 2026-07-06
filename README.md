# SEO Cannibalization Explorer

Streamlit app to explore edstellar.com queries where **exactly two pages compete**,
with a slider to filter by how close their average positions are (the position gap).

Data window: 2026-04-05 → 2026-07-03 (Google Search Console). 1,225 two-page conflicts.

## Files
- `app.py` — the Streamlit app
- `cannibalization_data.csv` — the data it reads
- `requirements.txt` — dependencies

## Run locally
```bash
pip install -r requirements.txt
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
