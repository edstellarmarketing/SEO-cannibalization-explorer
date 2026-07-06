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


import os as _os

# Time-range snapshots: label -> csv file (only those present are offered)
RANGE_FILES = {
    "Last 90 days": "cannibalization_data_90.csv",
    "Last 28 days": "cannibalization_data_28.csv",
    "Last 7 days": "cannibalization_data_7.csv",
}


@st.cache_data
def load_data(csv_file: str):
    return pd.read_csv(csv_file)


def available_ranges():
    avail = {k: v for k, v in RANGE_FILES.items() if _os.path.exists(v)}
    if not avail and _os.path.exists("cannibalization_data.csv"):
        avail = {"All data": "cannibalization_data.csv"}
    return avail


@st.cache_data(show_spinner=False)
def fetch_page(path: str, nonce: int = 0) -> dict:
    """Fetch a page and extract title, meta description, headings, and body text.

    `nonce` is part of the cache key only — bump it to force a fresh fetch.
    """
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
    return {"url": url, "title": title, "meta": meta, "headings": headings[:50], "body": body[:9000]}


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
        "You are a senior SEO editor resolving keyword cannibalization on edstellar.com.\n"
        "Produce a DETAILED, copy-paste-ready fix with the ACTUAL FINAL CONTENT — not advice. "
        "Where you say to change something, write the exact replacement text.\n\n"
        f'Two pages both rank for the query: "{query}".\n'
        f"- Page A: {ca['url']} (avg position {pos_a})\n"
        f"- Page B: {cb['url']} (avg position {pos_b})\n\n"
        "Their extracted content:\n\n"
        + _page_block("PAGE A", ca)
        + "\n"
        + _page_block("PAGE B", cb)
        + "\n\nRespond in markdown with these sections:\n\n"
        "## 1. Decision — Consolidate or Differentiate\n"
        "First choose ONE strategy and justify it against the actual content above:\n"
        "- **CONSOLIDATE (301 merge)** — redirect the weaker page entirely into the winner. "
        "Choose this when the two pages are near-duplicates / serve the SAME search intent, or the "
        "weaker page has little unique value worth keeping.\n"
        "- **DIFFERENTIATE (keep both)** — keep both URLs and rewrite BOTH to target distinct "
        "intents, removing the overlap from EACH. Choose this when the two pages can own genuinely "
        "separable intents and both hold unique value.\n"
        "State the verdict in bold (**CONSOLIDATE** or **DIFFERENTIATE**), then 2–3 sentences of "
        "reasoning citing the specific overlapping vs. unique sections you see above.\n\n"
        f'## 2. Winner / surviving URL\nWhich URL should own "{query}" (and survive if consolidating).\n\n'
        "## 3. Action — write the FINAL content for the chosen strategy\n\n"
        "**If you chose CONSOLIDATE:**\n"
        "- State clearly: which URL is redirected → which URL survives.\n"
        "- The exact 301 rule (from-path → to-path).\n"
        "- **Merge content**: list the unique sections worth salvaging from the redirected page, and "
        "for each give the FINAL heading + full paragraph text (ready to paste) to add into the "
        "surviving page so no value is lost.\n\n"
        "**If you chose DIFFERENTIATE:**\n"
        "- State the distinct target intent for EACH page in one line each.\n"
        "- Then, for **BOTH pages** (do Page A and Page B separately), give FINAL **Before → After** "
        "content that removes the overlap from that page:\n"
        "  - **Title tag** — Before / After (≤ 60 chars)\n"
        "  - **Meta description** — Before / After (≤ 155 chars)\n"
        "  - **H1** — Before / After\n"
        "  - **Each overlapping heading/section** — quote the current heading, then give the "
        "rewritten heading AND the full rewritten paragraph (final wording, ready to paste) that "
        "shifts it toward that page's distinct intent. Remove/absorb duplicated ground on BOTH sides.\n"
        "- Any NEW section to add to the winner to fully own the query (final heading + paragraph/FAQ text).\n\n"
        "## 4. Technical fixes\n"
        "- Exact `<link rel=\"canonical\">` line(s) — self-canonical if differentiating; canonical the "
        "redirected page to the survivor if consolidating.\n"
        "- Internal links: exact anchor text + target URL in BOTH directions (differentiate case).\n"
        "- Confirm the 301 rule again if consolidating.\n\n"
        "Rules: WRITE the final titles, metas, headings, and paragraphs verbatim — do not describe "
        "what to write. Reference the real headings/text shown above. Be thorough and specific. "
        "Output ONLY the markdown report starting at '## 1. Decision' — no preamble, no sign-off, "
        "no meta-commentary about your process."
    )


@st.cache_data(show_spinner=False)
def get_optimization_advice(query, page_a, pos_a, page_b, pos_b, nonce: int = 0) -> dict:
    """Fetch both pages and ask the Claude headless CLI what to optimize.

    `nonce` busts the cache so the Re-fetch button forces a fresh run.
    """
    exe = shutil.which("claude")
    if not exe:
        return {"error": "Run this app on your local machine to use the Fix button."}
    ca, cb = fetch_page(page_a, nonce), fetch_page(page_b, nonce)
    prompt = build_prompt(query, page_a, pos_a, page_b, pos_b, ca, cb)
    try:
        res = subprocess.run(
            [exe, "-p", prompt],
            capture_output=True,
            text=True,
            timeout=360,
            stdin=subprocess.DEVNULL,  # don't wait for stdin
            env=os.environ.copy(),  # carries CLAUDE_CODE_OAUTH_TOKEN from .env
        )
    except subprocess.TimeoutExpired:
        return {"error": "Claude timed out after 360s."}
    if res.returncode != 0:
        return {"error": (res.stderr or "claude exited non-zero").strip()}
    return {"advice": res.stdout.strip()}


st.title("🔎 SEO Cannibalization Explorer")
st.caption(
    "Queries where **exactly two pages** compete. Use the slider to keep only "
    "conflicts where the two pages rank close together — a small position gap "
    "means they are genuinely fighting each other."
)

# ---- Time range -------------------------------------------------------------
st.sidebar.header("Time range")
_ranges = available_ranges()
range_label = st.sidebar.selectbox("Data window", list(_ranges.keys()), index=0)
df = load_data(_ranges[range_label])

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
one_per_pair = st.sidebar.checkbox(
    "One row per page pair",
    value=True,
    help="Collapse reverse/duplicate queries (e.g. 'ceo vs coo' and 'coo vs ceo') that point to "
         "the same two pages. Keeps the highest-impression query as the representative.",
)

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

# Collapse reverse/duplicate queries that point to the same unordered page pair,
# keeping the highest-impression query as the representative row.
if one_per_pair and not f.empty:
    pair_key = f.apply(lambda r: tuple(sorted((r["page_a"], r["page_b"]))), axis=1)
    f = (
        f.assign(_pair=pair_key)
        .sort_values("total_impressions", ascending=False)
        .drop_duplicates("_pair", keep="first")
        .drop(columns="_pair")
    )

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

# ---- Claude optimization advice (shown at top, above the table) -------------
if "action_row" in st.session_state:
    ar = st.session_state["action_row"]
    sig = f"{ar['query']}|{ar['page_a']}|{ar['page_b']}"
    nonce_key = f"nonce_{sig}"
    nonce = st.session_state.get(nonce_key, 0)
    with st.container(border=True):
        cols_hdr = st.columns([5, 1, 1])
        cols_hdr[0].subheader(f"🔧 How to fix: “{ar['query']}”")
        if cols_hdr[1].button("🔄 Re-fetch", help="Fetch both pages fresh and re-run Claude (bypass cache)"):
            st.session_state[nonce_key] = nonce + 1
            st.rerun()
        if cols_hdr[2].button("✕ Close"):
            del st.session_state["action_row"]
            st.rerun()
        st.caption(f"{ar['page_a']}  (pos {ar['pos_a']})   ↔   {ar['page_b']}  (pos {ar['pos_b']})")
        with st.spinner("Fetching both pages and asking Claude for the full rewrite… (can take 1–3 min)"):
            result = get_optimization_advice(
                ar["query"], ar["page_a"], ar["pos_a"], ar["page_b"], ar["pos_b"], nonce
            )
        if result.get("error"):
            st.error(result["error"])
        else:
            st.markdown(result["advice"])
            if nonce:
                st.caption(f"🔄 Fetched fresh (re-fetch #{nonce}).")
    st.divider()

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
        st.rerun()  # jump straight to the result panel at the top

if len(f) > len(view):
    st.caption(f"Showing first {len(view)} of {len(f):,} rows. Increase 'Rows to display' to see more.")

# ---- Download filtered view -------------------------------------------------
st.download_button(
    "⬇ Download filtered CSV",
    data=f.to_csv(index=False).encode("utf-8"),
    file_name=f"cannibalization_gap_{max_gap}.csv",
    mime="text/csv",
)
