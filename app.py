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

f = f.sort_values("total_impressions", ascending=False)

# ---- Summary metrics --------------------------------------------------------
c1, c2, c3 = st.columns(3)
c1.metric("Conflicts shown", f"{len(f):,}")
c2.metric("Total conflicts (2-page)", f"{len(df):,}")
c3.metric("Impressions in view", f"{int(f['total_impressions'].sum()):,}")

st.markdown(
    f"Showing queries with **2 competing pages** and a position gap **≤ {max_gap}**"
    + (f" and **≥ {min_impr:,}** impressions." if min_impr else ".")
)

# ---- Table ------------------------------------------------------------------
st.dataframe(
    f,
    use_container_width=True,
    hide_index=True,
    column_config={
        "query": "Query",
        "total_impressions": st.column_config.NumberColumn("Impressions", format="%d"),
        "pos_gap": st.column_config.NumberColumn("Pos gap", format="%.1f"),
        "page_a": "Page A",
        "pos_a": st.column_config.NumberColumn("Pos A", format="%.1f"),
        "impr_a": st.column_config.NumberColumn("Impr A", format="%d"),
        "page_b": "Page B",
        "pos_b": st.column_config.NumberColumn("Pos B", format="%.1f"),
        "impr_b": st.column_config.NumberColumn("Impr B", format="%d"),
    },
)

# ---- Download filtered view -------------------------------------------------
st.download_button(
    "⬇ Download filtered CSV",
    data=f.to_csv(index=False).encode("utf-8"),
    file_name=f"cannibalization_gap_{max_gap}.csv",
    mime="text/csv",
)
