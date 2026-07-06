"""
SEO Cannibalization Explorer — edstellar.com
Queries where exactly two pages compete, filterable by how close their
average positions are (the position gap).

Data: cannibalization_data.csv (generated from Google Search Console,
window 2026-04-05 -> 2026-07-03).
"""

import os
import shutil
import subprocess

import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()  # read CLAUDE_CODE_OAUTH_TOKEN (and anything else) from a local .env

st.set_page_config(page_title="SEO Cannibalization Explorer", page_icon="🔎", layout="wide")

BASE_URL = "https://www.edstellar.com"


def claude_auth_status():
    """Return (ok: bool, message: str) describing headless-CLI readiness."""
    if not shutil.which("claude"):
        return False, "Run this app on your local machine to use the Fix button."
    if os.environ.get("CLAUDE_CODE_OAUTH_TOKEN"):
        return True, "Authenticated via subscription token (CLAUDE_CODE_OAUTH_TOKEN)."
    return True, ("No CLAUDE_CODE_OAUTH_TOKEN in .env — will use whatever login `claude` "
                  "already has. Run `claude setup-token` and add it to .env for a stable subscription auth.")


@st.cache_data
def load_data():
    df = pd.read_csv("cannibalization_data.csv")
    return df


@st.cache_data(show_spinner=False)
def fetch_page(path: str) -> dict:
    """Fetch a page and extract title, meta description, headings, and body text."""
    url = BASE_URL.rstrip("/") + "/" + path.lstrip("/")
    try:
        resp = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0 (cannibalization-explorer)"})
        resp.raise_for_status()
    except Exception as e:  # noqa: BLE001
        return {"url": url, "error": str(e)}
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    title = (soup.title.string or "").strip() if soup.title else ""
    md = soup.find("meta", attrs={"name": "description"})
    meta = md.get("content", "").strip() if md else ""
    headings = [f"{h.name.upper()}: {h.get_text(' ', strip=True)}" for h in soup.find_all(["h1", "h2", "h3"])]
    body = " ".join(soup.get_text(" ", strip=True).split())
    return {"url": url, "title": title, "meta": meta, "headings": headings[:40], "body": body[:6000]}


def _page_block(label: str, p: dict) -> str:
    if p.get("error"):
        return f"=== {label}: {p['url']} ===\n(could not fetch: {p['error']})\n"
    return (
        f"=== {label}: {p['url']} ===\n"
        f"Title: {p['title']}\n"
        f"Meta description: {p['meta']}\n"
        f"Headings:\n- " + "\n- ".join(p["headings"]) + "\n"
        f"Body excerpt:\n{p['body']}\n"
    )


def build_prompt(query, page_a, pos_a, page_b, pos_b, ca, cb) -> str:
    return (
        "You are an SEO expert resolving keyword cannibalization on edstellar.com.\n\n"
        f'Two pages both rank for the query: "{query}".\n'
        f"- Page A: {ca['url']} (avg position {pos_a})\n"
        f"- Page B: {cb['url']} (avg position {pos_b})\n\n"
        "Their extracted content:\n\n"
        + _page_block("PAGE A", ca)
        + "\n"
        + _page_block("PAGE B", cb)
        + "\n\nGive a concrete fix. In markdown, under 400 words:\n"
        f'1. **Winner**: which page should own "{query}" and why (1 line).\n'
        "2. **Edit the other page**: name the EXACT overlapping headings/sections to remove, "
        "rewrite, or re-target (quote the actual heading text you see above) and say what intent it should target instead.\n"
        "3. **Strengthen the winner**: what section/heading/content to add or expand.\n"
        "4. **Technical**: canonical, internal-link anchor, or 301 recommendation.\n"
        "Reference the real headings/text above — do not be generic."
    )


@st.cache_data(show_spinner=False)
def get_optimization_advice(query, page_a, pos_a, page_b, pos_b) -> dict:
    """Fetch both pages and ask the Claude headless CLI what to optimize."""
    exe = shutil.which("claude")
    if not exe:
        return {"error": "Run this app on your local machine to use the Fix button."}
    ca, cb = fetch_page(page_a), fetch_page(page_b)
    prompt = build_prompt(query, page_a, pos_a, page_b, pos_b, ca, cb)
    try:
        res = subprocess.run(
            [exe, "-p", prompt],
            capture_output=True,
            text=True,
            timeout=240,
            env=os.environ.copy(),  # carries CLAUDE_CODE_OAUTH_TOKEN from .env
        )
    except subprocess.TimeoutExpired:
        return {"error": "Claude timed out after 240s."}
    if res.returncode != 0:
        return {"error": (res.stderr or "claude exited non-zero").strip()}
    return {"advice": res.stdout.strip()}


df = load_data()

st.title("🔎 SEO Cannibalization Explorer")
st.caption(
    "Queries where **exactly two pages** compete. Use the slider to keep only "
    "conflicts where the two pages rank close together — a small position gap "
    "means they are genuinely fighting each other."
)

# ---- Claude auth status -----------------------------------------------------
_ok, _msg = claude_auth_status()
st.sidebar.header("Claude (headless CLI)")
(st.sidebar.success if _ok else st.sidebar.error)(_msg)

# ---- Sidebar controls -------------------------------------------------------
st.sidebar.header("Filters")

max_gap = st.sidebar.slider(
    "Max average position difference (gap)",
    min_value=0.0,
    max_value=float(round(df["pos_gap"].max())),
    value=3.0,
    step=0.1,
    help="Keep only queries where the two competing pages are within this many positions of each other.",
)

min_impr = st.sidebar.slider(
    "Min total impressions",
    min_value=0,
    max_value=int(df["total_impressions"].max()),
    value=0,
    step=50,
    help="Hide low-volume conflicts.",
)

query_search = st.sidebar.text_input("Search query text", "")
page_search = st.sidebar.text_input("Search page URL", "")

st.sidebar.header("Exclude")
skip_1word = st.sidebar.checkbox("Skip 1-word queries", value=False)
skip_2word = st.sidebar.checkbox("Skip 2-word queries", value=False)
skip_skills = st.sidebar.checkbox("Skip skills-in-demand cluster", value=False)
skip_corp = st.sidebar.checkbox("Skip corporate-training-companies cluster", value=False)

st.sidebar.header("Sort")
SORT_OPTIONS = {
    "Pos A (low → high)": ("pos_a", True),
    "Pos B (low → high)": ("pos_b", True),
    "Position gap (low → high)": ("pos_gap", True),
    "Impressions (high → low)": ("total_impressions", False),
}
sort_choice = st.sidebar.selectbox("Sort by", list(SORT_OPTIONS.keys()), index=0)
sort_col, sort_asc = SORT_OPTIONS[sort_choice]

# ---- Apply filters ----------------------------------------------------------
f = df[(df["pos_gap"] <= max_gap) & (df["total_impressions"] >= min_impr)]

if query_search.strip():
    f = f[f["query"].str.contains(query_search.strip(), case=False, na=False)]

if page_search.strip():
    s = page_search.strip()
    f = f[
        f["page_a"].str.contains(s, case=False, na=False)
        | f["page_b"].str.contains(s, case=False, na=False)
    ]

# Word-count exclusions
word_count = f["query"].str.split().str.len()
if skip_1word:
    f = f[word_count != 1]
    word_count = f["query"].str.split().str.len()
if skip_2word:
    f = f[word_count != 2]


def _touches(frame, needle):
    return frame["page_a"].str.contains(needle, na=False) | frame[
        "page_b"
    ].str.contains(needle, na=False)


# Cluster exclusions (drop the conflict if either competing page is in the cluster)
if skip_skills:
    f = f[~_touches(f, "skills-in-demand")]
if skip_corp:
    f = f[~_touches(f, "corporate-training-companies")]

f = f.sort_values(sort_col, ascending=sort_asc)

# ---- Summary metrics --------------------------------------------------------
c1, c2, c3 = st.columns(3)
c1.metric("Conflicts shown", f"{len(f):,}")
c2.metric("Total conflicts (2-page)", f"{len(df):,}")
c3.metric("Impressions in view", f"{int(f['total_impressions'].sum()):,}")

st.markdown(
    f"Showing queries with **2 competing pages** and a position gap **≤ {max_gap}**"
    + (f" and **≥ {min_impr:,}** impressions." if min_impr else ".")
)

# ---- Table (custom, with an Action button column) ---------------------------
# Cap how many rows render buttons (one st.button per row is expensive).
row_limit = st.number_input(
    "Rows to display", min_value=10, max_value=500, value=50, step=10
)
view = f.head(int(row_limit))

# column layout: query, impr, gap, page_a, posA, imprA, page_b, posB, imprB, action
WIDTHS = [3, 1.1, 0.9, 3, 0.8, 1, 3, 0.8, 1, 1.2]
HEADERS = [
    "Query", "Impr", "Gap", "Page A", "Pos A", "Impr A",
    "Page B", "Pos B", "Impr B", "Action",
]

head_cols = st.columns(WIDTHS)
for col, label in zip(head_cols, HEADERS):
    col.markdown(f"**{label}**")

for idx, r in view.iterrows():
    cols = st.columns(WIDTHS)
    cols[0].write(r["query"])
    cols[1].write(f"{int(r['total_impressions']):,}")
    cols[2].write(f"{r['pos_gap']:.1f}")
    cols[3].write(r["page_a"])
    cols[4].write(f"{r['pos_a']:.1f}")
    cols[5].write(f"{int(r['impr_a']):,}")
    cols[6].write(r["page_b"])
    cols[7].write(f"{r['pos_b']:.1f}")
    cols[8].write(f"{int(r['impr_b']):,}")
    if cols[9].button("🔧 Fix", key=f"action_{idx}", help="Ask Claude what to optimize"):
        st.session_state["action_row"] = r.to_dict()

if len(f) > len(view):
    st.caption(f"Showing first {len(view)} of {len(f):,} rows. Increase 'Rows to display' to see more.")

# ---- Claude optimization advice --------------------------------------------
if "action_row" in st.session_state:
    ar = st.session_state["action_row"]
    st.divider()
    st.subheader(f"🔧 How to fix: “{ar['query']}”")
    st.caption(f"{ar['page_a']}  (pos {ar['pos_a']})   ↔   {ar['page_b']}  (pos {ar['pos_b']})")
    with st.spinner("Fetching both pages and asking Claude…"):
        result = get_optimization_advice(
            ar["query"], ar["page_a"], ar["pos_a"], ar["page_b"], ar["pos_b"]
        )
    if result.get("error"):
        st.error(result["error"])
    else:
        st.markdown(result["advice"])
    if st.button("Clear result"):
        del st.session_state["action_row"]
        st.rerun()

# ---- Download filtered view -------------------------------------------------
st.download_button(
    "⬇ Download filtered CSV",
    data=f.to_csv(index=False).encode("utf-8"),
    file_name=f"cannibalization_gap_{max_gap}.csv",
    mime="text/csv",
)
