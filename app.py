"""
SEO Cannibalization Explorer — edstellar.com
Queries where exactly two pages compete, filterable by how close their
average positions are (the position gap).

Data: cannibalization_data.csv (generated from Google Search Console,
window 2026-04-05 -> 2026-07-03).
"""

import pandas as pd
import streamlit as st

st.set_page_config(page_title="SEO Cannibalization Explorer", page_icon="🔎", layout="wide")


@st.cache_data
def load_data():
    df = pd.read_csv("cannibalization_data.csv")
    return df


df = load_data()

st.title("🔎 SEO Cannibalization Explorer")
st.caption(
    "Queries where **exactly two pages** compete. Use the slider to keep only "
    "conflicts where the two pages rank close together — a small position gap "
    "means they are genuinely fighting each other."
)

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
    if cols[9].button("Action", key=f"action_{idx}"):
        st.session_state["action_row"] = r.to_dict()

if len(f) > len(view):
    st.caption(f"Showing first {len(view)} of {len(f):,} rows. Increase 'Rows to display' to see more.")

# ---- Placeholder for the (to-be-defined) action ----------------------------
if "action_row" in st.session_state:
    ar = st.session_state["action_row"]
    st.info(
        f"🔧 Action clicked for query **'{ar['query']}'**  "
        f"({ar['page_a']}  ↔  {ar['page_b']}).  "
        "Behaviour to be defined."
    )

# ---- Download filtered view -------------------------------------------------
st.download_button(
    "⬇ Download filtered CSV",
    data=f.to_csv(index=False).encode("utf-8"),
    file_name=f"cannibalization_gap_{max_gap}.csv",
    mime="text/csv",
)
