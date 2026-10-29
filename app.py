"""Interactive sales dashboard: upload a sales Excel or CSV file and explore it.

Run:
    streamlit run app.py
"""
import pandas as pd
import plotly.express as px
import streamlit as st

import sales

AMBER, NAVY, GREEN, BLUE, CORAL, VIOLET = "#FFC42E", "#14213D", "#7CC68D", "#5B8DEF", "#E06C5A", "#9B8AF0"
PALETTE = [AMBER, BLUE, GREEN, CORAL, VIOLET, "#4FC1C9"]
CHART = dict(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
             margin=dict(l=8, r=8, t=8, b=8), height=330, font=dict(size=13),
             legend=dict(orientation="h", y=1.08, x=0, title=None))

st.set_page_config(page_title="Sales Dashboard", layout="wide")


@st.cache_data
def load(source, name):
    return sales.load(source, name)


def money(value):
    return f"{value:,.0f} EGP"


def delta(now, before):
    pct = sales.change(now, before)
    return None if pct is None else f"{pct:+.1f}% vs previous period"


# ---- Data -------------------------------------------------------------------------------------------
with st.sidebar:
    st.header("Data")
    upload = st.file_uploader("Upload a sales file", type=["xlsx", "xls", "csv"],
                              help="Needs a date column and a revenue column. Other columns are optional.")
try:
    data = load(upload, upload.name) if upload else load(sales.SAMPLE, sales.SAMPLE.name)
except sales.MissingColumns as e:
    st.error(str(e))
    st.stop()
source_name = upload.name if upload else f"{sales.SAMPLE.name} (sample data)"

# ---- Filters ----------------------------------------------------------------------------------------
with st.sidebar:
    st.header("Filters")
    first, last = data["date"].min().date(), data["date"].max().date()
    period = st.date_input("Dates", value=(first, last), min_value=first, max_value=last)
    start, end = (period if isinstance(period, tuple) and len(period) == 2 else (first, last))
    choices = {}
    for column, label, everything in (("branch", "Branch", "All branches"), ("category", "Category", "All categories"),
                                      ("channel", "Channel", "All channels")):
        if column in data:
            options = sorted(data[column].dropna().unique())
            choices[column] = st.multiselect(label, options, placeholder=everything)

view = sales.apply_filters(data, start, end, **choices)
before = sales.previous_period(data, start, end, **choices)

# ---- Header and KPIs --------------------------------------------------------------------------------
st.title("Sales Dashboard")
st.caption(f"{source_name} · {len(view):,} of {len(data):,} rows · {start:%d %b %Y} to {end:%d %b %Y}")

if view.empty:
    st.warning("No sales match these filters.")
    st.stop()

now = sales.kpis(view)
was = sales.kpis(before) if before is not None and not before.empty else {}
cols = st.columns(4)
cols[0].metric("Revenue", money(now["revenue"]), delta(now["revenue"], was.get("revenue")))
cols[1].metric("Orders", f"{now['orders']:,}", delta(now["orders"], was.get("orders")))
cols[2].metric("Average order", money(now["avg_order"]), delta(now["avg_order"], was.get("avg_order")))
if now["units"] is not None:
    cols[3].metric("Units sold", f"{now['units']:,}", delta(now["units"], was.get("units")))

# ---- Charts -----------------------------------------------------------------------------------------
left, right = st.columns([3, 2])
with left:
    st.subheader("Revenue by month")
    split = "channel" if "channel" in view else None
    month = sales.monthly(view, split_by=split)
    fig = px.bar(month, x="month", y="revenue", color=split, color_discrete_sequence=[AMBER, BLUE],
                 labels={"revenue": "Revenue (EGP)", "month": ""})
    fig.update_layout(**CHART)
    fig.update_xaxes(dtick="M1", tickformat="%b")
    st.plotly_chart(fig, width="stretch")
with right:
    if "branch" in view:
        st.subheader("Revenue by branch")
        by_branch = sales.revenue_by(view, "branch").sort_values("revenue")
        fig = px.bar(by_branch, x="revenue", y="branch", orientation="h", color_discrete_sequence=[AMBER],
                     labels={"revenue": "Revenue (EGP)", "branch": ""}, text_auto=".3s")
        fig.update_layout(**CHART)
        st.plotly_chart(fig, width="stretch")

left, right = st.columns([2, 3])
with left:
    if "category" in view:
        st.subheader("Revenue by category")
        fig = px.pie(sales.revenue_by(view, "category"), names="category", values="revenue", hole=0.55,
                     color_discrete_sequence=PALETTE)
        fig.update_layout(**CHART)
        fig.update_traces(textinfo="percent+label", showlegend=False)
        st.plotly_chart(fig, width="stretch")
with right:
    if "product" in view:
        st.subheader("Top 10 products")
        top = sales.revenue_by(view, "product", top=10).sort_values("revenue")
        fig = px.bar(top, x="revenue", y="product", orientation="h", color_discrete_sequence=[BLUE],
                     labels={"revenue": "Revenue (EGP)", "product": ""}, text_auto=".3s")
        fig.update_layout(**CHART)
        st.plotly_chart(fig, width="stretch")

# ---- Data and download ------------------------------------------------------------------------------
with st.expander("See the filtered rows"):
    st.dataframe(view, width="stretch", hide_index=True)
st.download_button("Download filtered data (Excel)", sales.to_excel(view), file_name="filtered_sales.xlsx",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
