"""
Validation -- data quality score and validation issues for a selected upload
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent))
sys.path.append(str(Path(__file__).resolve().parent.parent / "common"))
sys.path.append(str(Path(__file__).resolve().parent.parent / "forecasting"))

import streamlit as st
import plotly.express as px

from shared_utils import get_connection, render_upload_selector
from styles import load_custom_css, gradient_header, powerbi_kpi, status_badge
from chart_theme import apply_theme
from earnings_quality import compute_accruals_ratio, compute_revenue_receivables_divergence, get_red_flag_summary
from revenue_forecast import get_historical_data

st.set_page_config(page_title="Validation", layout="wide")
load_custom_css()
gradient_header("Data Validation", "Quality score and flagged issues for the selected company")

conn = get_connection()
upload_id, company_name = render_upload_selector(conn)

st.divider()

score_row = conn.execute("""
    SELECT score, total_issues, high_severity, medium_severity, low_severity
    FROM quality_scores WHERE upload_id = ?
""", [upload_id]).fetchdf()

if score_row.empty:
    st.warning("No quality score found for this upload.")
else:
    s = score_row.iloc[0]
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1: powerbi_kpi("Quality Score", f"{int(s['score'])}/100")
    with col2: powerbi_kpi("Total Issues", str(int(s["total_issues"])))
    with col3: powerbi_kpi("High Severity", str(int(s["high_severity"])))
    with col4: powerbi_kpi("Medium Severity", str(int(s["medium_severity"])))
    with col5: powerbi_kpi("Low Severity", str(int(s["low_severity"])))

st.divider()

issues = conn.execute("""
    SELECT check_name, line_item, period, severity, message
    FROM validation_issues WHERE upload_id = ?
    ORDER BY CASE severity WHEN 'HIGH' THEN 1 WHEN 'MEDIUM' THEN 2 ELSE 3 END
""", [upload_id]).fetchdf()

if issues.empty:
    status_badge("Clean -- no validation issues found", "success")
    st.success(f"No validation issues found for {company_name}. Data looks clean.")
else:
    status_badge(f"{len(issues)} issue(s) found", "warning")
    st.subheader(f"Validation Issues for {company_name}")

    severity_counts = issues["severity"].value_counts().reset_index()
    severity_counts.columns = ["severity", "count"]
    fig = px.bar(severity_counts, x="severity", y="count", color="severity",
                 color_discrete_map={"HIGH": "#F87171", "MEDIUM": "#FBBF24", "LOW": "#34D399"})
    fig.update_layout(showlegend=False)
    st.plotly_chart(apply_theme(fig), use_container_width=True)

    st.dataframe(issues, use_container_width=True, hide_index=True)

st.divider()

# ---------------------------------------------------------------------
# Earnings Quality Red-Flags -- classic analyst checks beyond rule-based validation
# ---------------------------------------------------------------------
st.subheader("Earnings Quality Red-Flags")
st.caption("Classic signals analysts use to spot aggressive or low-quality earnings -- heuristics, not proof of wrongdoing.")

hist_df = get_historical_data(conn, upload_id)
red_flags = get_red_flag_summary(hist_df)

if red_flags:
    status_badge(f"{len(red_flags)} red flag(s) found", "warning")
    for warning in red_flags:
        st.warning(warning)
else:
    status_badge("No red flags detected", "success")
    st.success("No earnings-quality red flags detected in the available data.")

col1, col2 = st.columns(2)

with col1:
    st.markdown("#### Accruals Ratio")
    st.caption("(Net Income - Operating Cash Flow) / Total Assets. Flagged if > 10%.")
    accruals_df = compute_accruals_ratio(hist_df)
    if accruals_df.empty:
        st.info("Requires operating cash flow data, not available for this upload.")
    else:
        fig = px.bar(accruals_df, x="period", y="accruals_ratio",
                     color=accruals_df["flag"].map({True: "Flagged", False: "Normal"}),
                     color_discrete_map={"Flagged": "#DC2626", "Normal": "#059669"})
        fig.add_hline(y=0.10, line_dash="dash", line_color="#DC2626")
        fig.update_layout(showlegend=True, legend_title="")
        st.plotly_chart(apply_theme(fig), use_container_width=True)

with col2:
    st.markdown("#### Revenue vs. Receivables Growth")
    st.caption("Receivables growing much faster than revenue can signal loose recognition. Flagged if divergence > 15pts.")
    divergence_df = compute_revenue_receivables_divergence(hist_df)
    if divergence_df.empty:
        st.info("Not enough periods to compute growth divergence.")
    else:
        fig = px.bar(divergence_df, x="period", y=["revenue_growth", "ar_growth"], barmode="group")
        st.plotly_chart(apply_theme(fig), use_container_width=True)