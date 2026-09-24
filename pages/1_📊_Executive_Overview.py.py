"""
Executive Overview -- cross-company summary of everything uploaded
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent))
sys.path.append(str(Path(__file__).resolve().parent.parent / "common"))

import streamlit as st
import plotly.express as px

from shared_utils import get_connection
from styles import load_custom_css, gradient_header, powerbi_kpi
from chart_theme import apply_theme, kpi_gauge

st.set_page_config(page_title="Executive Overview", layout="wide")
load_custom_css()
gradient_header("Executive Overview", "Cross-company summary of everything uploaded")

conn = get_connection()

uploads = conn.execute("""
    SELECT upload_id, company_name, source_filename, uploaded_at
    FROM uploads ORDER BY uploaded_at DESC
""").fetchdf()

if uploads.empty:
    st.info("No companies uploaded yet. Go to the home page to upload a financial statement.")
    st.stop()

col1, col2 = st.columns(2)
with col1:
    powerbi_kpi("Companies Analyzed", str(uploads["company_name"].nunique()))
with col2:
    powerbi_kpi("Total Uploads", str(len(uploads)))

st.divider()

# ---------------------------------------------------------------------
# Data quality across all companies
# ---------------------------------------------------------------------
st.subheader("Data Quality by Company")

scores = conn.execute("""
    SELECT q.upload_id, u.company_name, q.score, q.total_issues,
           q.high_severity, q.medium_severity, q.low_severity
    FROM quality_scores q
    JOIN uploads u ON q.upload_id = u.upload_id
    ORDER BY q.score ASC
""").fetchdf()

if not scores.empty:
    gauge_col, bar_col = st.columns([1, 2])
    with gauge_col:
        avg_score = scores["score"].mean()
        st.plotly_chart(kpi_gauge(avg_score, "Average Data Quality", max_val=100), use_container_width=True)

    with bar_col:
        fig = px.bar(scores, x="company_name", y="score", color="score",
                     color_continuous_scale=["#F87171", "#8B5CF6", "#34D399"],
                     range_color=[0, 100],
                     labels={"score": "Quality Score", "company_name": "Company"})
        fig.update_layout(showlegend=False)
        st.plotly_chart(apply_theme(fig), use_container_width=True)

    st.dataframe(
        scores[["company_name", "score", "total_issues", "high_severity", "medium_severity", "low_severity"]],
        use_container_width=True, hide_index=True,
    )

st.divider()

# ---------------------------------------------------------------------
# Latest-period financial snapshot per company
# ---------------------------------------------------------------------
st.subheader("Latest Financial Snapshot")

snapshot = conn.execute("""
    WITH latest_period AS (
        SELECT upload_id, MAX(period) AS period
        FROM financial_data
        GROUP BY upload_id
    )
    SELECT u.company_name, fd.period, fd.line_item, fd.value
    FROM financial_data fd
    JOIN latest_period lp ON fd.upload_id = lp.upload_id AND fd.period = lp.period
    JOIN uploads u ON fd.upload_id = u.upload_id
    WHERE fd.line_item IN ('revenue', 'net_income', 'total_assets', 'total_equity')
""").fetchdf()

if not snapshot.empty:
    pivot = snapshot.pivot_table(index=["company_name", "period"], columns="line_item", values="value").reset_index()

    col_left, col_right = st.columns(2)
    with col_left:
        if "revenue" in pivot.columns:
            fig = px.bar(pivot, x="company_name", y="revenue", color="company_name",
                          title="Revenue (Most Recent Period)")
            fig.update_layout(showlegend=False)
            st.plotly_chart(apply_theme(fig), use_container_width=True)

    with col_right:
        if "net_income" in pivot.columns:
            fig = px.bar(pivot, x="company_name", y="net_income", color="company_name",
                          title="Net Income (Most Recent Period)")
            fig.update_layout(showlegend=False)
            st.plotly_chart(apply_theme(fig), use_container_width=True)

    st.dataframe(pivot, use_container_width=True, hide_index=True)

st.divider()

# ---------------------------------------------------------------------
# Key ratio comparison across companies (latest period)
# ---------------------------------------------------------------------
st.subheader("Key Ratio Comparison (Latest Period)")

ratio_snapshot = conn.execute("""
    WITH latest_period AS (
        SELECT upload_id, MAX(period) AS period
        FROM financial_ratios
        GROUP BY upload_id
    )
    SELECT u.company_name, fr.ratio_name, fr.value
    FROM financial_ratios fr
    JOIN latest_period lp ON fr.upload_id = lp.upload_id AND fr.period = lp.period
    JOIN uploads u ON fr.upload_id = u.upload_id
    WHERE fr.ratio_name IN ('net_margin_pct', 'return_on_equity_pct', 'current_ratio', 'debt_to_equity')
""").fetchdf()

if not ratio_snapshot.empty:
    key_ratio_labels = {
        "net_margin_pct": "Net Margin %",
        "return_on_equity_pct": "Return on Equity %",
        "current_ratio": "Current Ratio",
        "debt_to_equity": "Debt to Equity",
    }
    tabs = st.tabs(list(key_ratio_labels.values()))
    for tab, (ratio_key, ratio_label) in zip(tabs, key_ratio_labels.items()):
        with tab:
            data = ratio_snapshot[ratio_snapshot["ratio_name"] == ratio_key]
            if not data.empty:
                fig = px.bar(data, x="company_name", y="value", color="company_name",
                              title=ratio_label)
                fig.update_layout(showlegend=False)
                st.plotly_chart(apply_theme(fig), use_container_width=True)
else:
    st.info("No ratio data available yet.")

st.divider()

st.subheader("All Uploads")
st.dataframe(uploads, use_container_width=True, hide_index=True)