"""
Financial Health -- ratio analysis across all four categories
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent))
sys.path.append(str(Path(__file__).resolve().parent.parent / "common"))
sys.path.append(str(Path(__file__).resolve().parent.parent / "forecasting"))

import streamlit as st

from shared_utils import get_connection, render_upload_selector
from styles import load_custom_css, gradient_header, powerbi_kpi, status_badge
from chart_theme import area_line_chart, apply_theme
from dupont import compute_dupont_series, interpret_dupont_trend
from altman_zscore import compute_zscore_series, zone_status
from statement_analysis import compute_common_size, compute_horizontal
from chart_theme import kpi_gauge
from revenue_forecast import get_historical_data

st.set_page_config(page_title="Financial Health", layout="wide")
load_custom_css()
gradient_header("Financial Health", "Ratio analysis across profitability, liquidity, leverage, and efficiency")

conn = get_connection()
upload_id, company_name = render_upload_selector(conn)

st.divider()

ratios = conn.execute("""
    SELECT category, ratio_name, period, value
    FROM financial_ratios WHERE upload_id = ?
    ORDER BY category, ratio_name, period
""", [upload_id]).fetchdf()

if ratios.empty:
    st.warning(f"No ratios computed yet for {company_name}.")
    st.stop()

# ---------------------------------------------------------------------
# Headline KPI row -- latest value + delta vs prior period, for a
# curated set of ratios if they exist in this company's data
# ---------------------------------------------------------------------
headline_ratios = [
    ("net_margin_pct", "Net Margin", "%"),
    ("current_ratio", "Current Ratio", "x"),
    ("return_on_equity_pct", "Return on Equity", "%"),
    ("debt_to_equity", "Debt to Equity", "x"),
]

available = [(name, label, unit) for name, label, unit in headline_ratios
             if name in ratios["ratio_name"].unique()]

if available:
    cols = st.columns(len(available))
    for col, (ratio_name, label, unit) in zip(cols, available):
        series = ratios[ratios["ratio_name"] == ratio_name].sort_values("period")
        latest = series["value"].iloc[-1]
        delta_str, delta_positive = None, True
        if len(series) > 1:
            prior = series["value"].iloc[-2]
            change = latest - prior
            delta_positive = change >= 0
            delta_str = f"{change:+.2f}{unit} vs prior period"
        value_str = f"{latest:.2f}{unit}"
        with col:
            powerbi_kpi(label, value_str, delta_str, delta_positive=delta_positive)
    st.divider()

# ---------------------------------------------------------------------
# DuPont ROE Decomposition -- shows WHY ROE moved, not just that it did
# ---------------------------------------------------------------------
st.subheader("DuPont ROE Decomposition")
st.caption("ROE = Net Margin x Asset Turnover x Equity Multiplier -- profitability x efficiency x leverage")

hist_df = get_historical_data(conn, upload_id)
dupont_df = compute_dupont_series(hist_df)

if dupont_df.empty:
    st.info("Not enough data (revenue, net income, total assets, total equity) to compute DuPont decomposition.")
else:
    st.info(interpret_dupont_trend(dupont_df))

    dupont_cols = st.columns(4)
    latest = dupont_df.iloc[-1]
    with dupont_cols[0]:
        powerbi_kpi("Net Margin", f"{latest['net_margin']:.1%}")
    with dupont_cols[1]:
        powerbi_kpi("Asset Turnover", f"{latest['asset_turnover']:.2f}x")
    with dupont_cols[2]:
        powerbi_kpi("Equity Multiplier", f"{latest['equity_multiplier']:.2f}x")
    with dupont_cols[3]:
        powerbi_kpi("Resulting ROE", f"{latest['roe']:.1%}")

    import plotly.graph_objects as go
    fig = go.Figure()
    fig.add_bar(x=dupont_df["period"], y=dupont_df["net_margin"], name="Net Margin")
    fig.add_bar(x=dupont_df["period"], y=dupont_df["asset_turnover"], name="Asset Turnover")
    fig.add_bar(x=dupont_df["period"], y=dupont_df["equity_multiplier"], name="Equity Multiplier")
    fig.add_scatter(x=dupont_df["period"], y=dupont_df["roe"], name="ROE", mode="lines+markers", yaxis="y2")
    fig.update_layout(
        barmode="group",
        yaxis=dict(title="Component value"),
        yaxis2=dict(title="ROE", overlaying="y", side="right", tickformat=".0%"),
    )
    st.plotly_chart(apply_theme(fig), use_container_width=True)

    with st.expander("See DuPont data table"):
        display_df = dupont_df.copy()
        for col in ["net_margin", "roe"]:
            display_df[col] = display_df[col].apply(lambda v: f"{v:.1%}")
        for col in ["asset_turnover", "equity_multiplier"]:
            display_df[col] = display_df[col].apply(lambda v: f"{v:.2f}x")
        st.dataframe(display_df, use_container_width=True, hide_index=True)

st.divider()

# ---------------------------------------------------------------------
# Altman Z'-Score -- bankruptcy / financial distress risk indicator
# ---------------------------------------------------------------------
st.subheader("Altman Z'-Score: Financial Distress Risk")
st.caption("Private-firm model (book equity, not market cap) -- Safe > 2.90, Grey 1.23-2.90, Distress < 1.23")

zscore_df = compute_zscore_series(hist_df)

if zscore_df.empty:
    st.info("Not enough data (working capital, retained earnings, EBIT, equity, liabilities) to compute Z-Score.")
else:
    latest_z = zscore_df.iloc[-1]

    z_col1, z_col2 = st.columns([1, 2])
    with z_col1:
        st.plotly_chart(
            kpi_gauge(latest_z["zscore"], "Z'-Score", min_val=0, max_val=6),
            use_container_width=True,
        )
        status_badge(f"{latest_z['zone']} Zone", zone_status(latest_z["zone"]))

    with z_col2:
        import plotly.express as px
        fig = px.line(zscore_df, x="period", y="zscore", markers=True)
        fig.add_hline(y=2.90, line_dash="dash", line_color="#059669", annotation_text="Safe threshold")
        fig.add_hline(y=1.23, line_dash="dash", line_color="#DC2626", annotation_text="Distress threshold")
        st.plotly_chart(apply_theme(fig), use_container_width=True)

    with st.expander("See Z-Score component breakdown"):
        display_df = zscore_df.copy()
        display_df["zscore"] = display_df["zscore"].round(2)
        st.dataframe(display_df, use_container_width=True, hide_index=True)

st.divider()

st.subheader("Common-Size & Horizontal Analysis")
st.caption("Common-size: every line as % of revenue (income) or % of total assets (balance sheet). Horizontal: every line indexed to its first period = 100.")

statement_choice = st.radio("Statement", ["Income Statement", "Balance Sheet"], horizontal=True, key="statement_choice")
statement_key = "income" if statement_choice == "Income Statement" else "balance"
analysis_type = st.radio("View", ["Common-Size (%)", "Horizontal (Indexed to 100)"], horizontal=True, key="analysis_type")

if analysis_type == "Common-Size (%)":
    cs_df = compute_common_size(hist_df, statement_key)
    if cs_df.empty:
        st.info("Not enough data for common-size analysis on this statement.")
    else:
        display_cs = cs_df.set_index("line_item")
        display_cs.index = [i.replace("_", " ").title() for i in display_cs.index]
        st.dataframe(display_cs.style.format("{:.1%}", na_rep="-"), use_container_width=True)
        base_label = "Revenue" if statement_key == "income" else "Total Assets"
        st.caption(f"Every value shown as a percentage of {base_label} for that period.")
else:
    h_df = compute_horizontal(hist_df, statement_key)
    if h_df.empty:
        st.info("Not enough data for horizontal analysis on this statement.")
    else:
        display_h = h_df.set_index("line_item")
        display_h.index = [i.replace("_", " ").title() for i in display_h.index]
        st.dataframe(display_h.style.format("{:.1f}", na_rep="-"), use_container_width=True)
        st.caption("Every line indexed to its own first available period = 100. Values above 100 mean growth since the base period.")

st.divider()

st.subheader(f"Ratio Trends for {company_name}")

category_labels = {
    "profitability": "Profitability",
    "liquidity": "Liquidity",
    "leverage": "Leverage",
    "efficiency": "Efficiency",
}

tabs = st.tabs(list(category_labels.values()))

for tab, (category_key, category_label) in zip(tabs, category_labels.items()):
    with tab:
        cat_data = ratios[ratios["category"] == category_key]
        if cat_data.empty:
            st.info(f"No {category_label.lower()} ratios available.")
            continue

        ratio_names = cat_data["ratio_name"].unique()
        cols = st.columns(min(len(ratio_names), 3))

        for i, ratio_name in enumerate(ratio_names):
            single_ratio = cat_data[cat_data["ratio_name"] == ratio_name].sort_values("period")
            with cols[i % 3]:
                fig = area_line_chart(
                    single_ratio, x="period", y="value",
                    title=ratio_name.replace("_", " ").title(),
                )
                fig.update_layout(height=280)
                st.plotly_chart(fig, use_container_width=True)

        with st.expander(f"See {category_label.lower()} data table"):
            pivot = cat_data.pivot(index="ratio_name", columns="period", values="value")
            st.dataframe(pivot, use_container_width=True)

st.divider()

st.subheader("Compare all ratios in one view")
selected_category = st.selectbox("Filter by category", ["All"] + list(category_labels.values()))

if selected_category == "All":
    filtered = ratios
else:
    key = [k for k, v in category_labels.items() if v == selected_category][0]
    filtered = ratios[ratios["category"] == key]

pivot_all = filtered.pivot_table(index=["category", "ratio_name"], columns="period", values="value")
st.dataframe(pivot_all, use_container_width=True)