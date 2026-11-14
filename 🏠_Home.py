"""
AI-POWERED FINANCIAL INTELLIGENCE PLATFORM - HOME & DASHBOARD
Clean entry point connecting all modules, presenting key operational metrics,
active company switcher, and audit lineage.
"""
import sys
from pathlib import Path
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings
from app.database.connection import db_manager
from app.database.repositories import CompanyRepository, FinancialFactRepository, ValuationRepository
from app.ui.components import load_terminal_theme, render_disclaimer

st.set_page_config(
    page_title="AI Financial Intelligence Platform",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)
load_terminal_theme()

# Sidebar: Global Context
with st.sidebar:
    st.title("🏦 Financial Platform")
    st.caption("Institutional Financial Analytics & Valuation")
    st.divider()

    conn = db_manager.get_connection()
    comp_repo = CompanyRepository(conn)
    companies = comp_repo.list_all()

    if not companies:
        # Seed default company if empty
        from app.schemas.financial import Company
        default_co = Company(company_id="co_apple", name="Apple Inc.", ticker="AAPL", reporting_currency="USD")
        comp_repo.create(default_co)
        companies = [default_co]

    company_options = {c.name: c.company_id for c in companies}
    selected_name = st.selectbox("Active Company", list(company_options.keys()))
    selected_company_id = company_options[selected_name]

    st.session_state["active_company_id"] = selected_company_id
    st.session_state["active_company_name"] = selected_name

    st.divider()
    st.caption("Environment: Development")
    st.caption(f"DuckDB: {settings.resolved_db_path.name}")

# Main Header
st.title("📊 Executive Overview & Analysis")
st.subheader(f"Entity Scope: {selected_name} ({selected_company_id})")

# Fetch latest figures for selected company
fact_repo = FinancialFactRepository(conn)
val_repo = ValuationRepository(conn)

facts = conn.execute(
    """
    SELECT f.canonical_item, f.period, f.normalized_value, f.normalized_currency
    FROM financial_facts f
    JOIN datasets d ON f.dataset_id = d.dataset_id
    JOIN dataset_versions v ON f.dataset_id = v.dataset_id AND f.dataset_version = v.version
    WHERE d.company_id = ? AND v.is_active = TRUE
    ORDER BY f.period DESC
    """,
    [selected_company_id]
).fetchdf()

val_data = conn.execute(
    """
    SELECT vr.enterprise_value, vr.equity_value, vr.wacc, vr.terminal_growth_rate, vr.implied_share_price
    FROM valuation_runs vr
    JOIN datasets d ON vr.dataset_id = d.dataset_id
    WHERE d.company_id = ?
    ORDER BY vr.created_at DESC LIMIT 1
    """,
    [selected_company_id]
).fetchone()

# Render Top KPIs (Honest UI: empty state if not yet uploaded)
kpi1, kpi2, kpi3, kpi4 = st.columns(4)

if not facts.empty:
    latest_period = facts["period"].iloc[0]
    rev_fact = facts[facts["canonical_item"] == "revenue"]
    latest_rev = rev_fact["normalized_value"].iloc[0] if not rev_fact.empty else 0.0

    ebit_fact = facts[facts["canonical_item"] == "operating_income"]
    latest_ebit = ebit_fact["normalized_value"].iloc[0] if not ebit_fact.empty else 0.0

    ev = val_data[0] if val_data else None
    share_price = val_data[4] if val_data else None

    with kpi1:
        st.metric(f"Revenue ({latest_period})", f"${latest_rev:,.0f}")
    with kpi2:
        st.metric(f"Operating Income ({latest_period})", f"${latest_ebit:,.0f}")
    with kpi3:
        st.metric("DCF Enterprise Value", f"${ev:,.0f}" if ev else "Not Run")
    with kpi4:
        st.metric("Implied Share Price", f"${share_price:,.2f}" if share_price else "Not Run")
else:
    with kpi1:
        st.metric("Revenue", "No Data")
    with kpi2:
        st.metric("Operating Income", "No Data")
    with kpi3:
        st.metric("Enterprise Value", "No Data")
    with kpi4:
        st.metric("Implied Share Price", "No Data")

st.divider()

# Historical Visualizations
col_chart1, col_chart2 = st.columns(2)

with col_chart1:
    st.markdown("### 📈 Revenue & Earnings History")
    if not facts.empty:
        trend_df = facts[facts["canonical_item"].isin(["revenue", "operating_income", "net_income"])].copy()
        if not trend_df.empty:
            fig = px.bar(
                trend_df,
                x="period",
                y="normalized_value",
                color="canonical_item",
                barmode="group",
                title=f"Historical Financials ({selected_name})",
                labels={"normalized_value": "Amount (USD)", "period": "Period", "canonical_item": "Metric"},
                template="plotly_dark",
            )
            fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No revenue or income statement items uploaded yet.")
    else:
        st.info("Upload statements on the 'Upload & Ingest' page to generate historical charts.")

with col_chart2:
    st.markdown("### 🔍 Data Quality & Compliance Status")
    q_score = conn.execute(
        """
        SELECT vr.overall_quality_score, vr.completeness_score, vr.mapping_quality_score,
               vr.accounting_consistency_score, vr.anomaly_severity_score
        FROM validation_runs vr
        JOIN datasets d ON vr.dataset_id = d.dataset_id
        WHERE d.company_id = ?
        ORDER BY vr.executed_at DESC LIMIT 1
        """,
        [selected_company_id]
    ).fetchone()

    if q_score:
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number",
            value=q_score[0],
            title={"text": "Overall Data Quality Score"},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": "#38BDF8"},
                "steps": [
                    {"range": [0, 40], "color": "#EF4444"},
                    {"range": [40, 75], "color": "#F59E0B"},
                    {"range": [75, 100], "color": "#10B981"},
                ],
            }
        ))
        fig_gauge.update_layout(paper_bgcolor="rgba(0,0,0,0)", font_color="#F8FAFC", height=320)
        st.plotly_chart(fig_gauge, use_container_width=True)
    else:
        st.info("No data quality checks run yet for active company.")

# Mandatory academic research disclaimer
render_disclaimer()