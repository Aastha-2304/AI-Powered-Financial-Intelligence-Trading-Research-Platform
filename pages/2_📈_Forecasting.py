"""
Page 2: Exploratory Financial Analysis & Forecasting Engine
AI-Powered Financial Intelligence Platform

Features:
- Exploratory Data Analysis (EDA): Common-size statements, margin trends, liquidity & leverage ratios
- Driver-Based 5-Year Projections: Revenue growth, operating margins, working capital days (DSO/DIO/DPO), debt schedule
- Free Cash Flow (FCF) schedule derivation for DCF valuation
- Baseline Model Comparison: Holt's Exponential Smoothing, Moving Average, Naive Last Value
- Backtesting Evaluation: MAPE, RMSE, and MAE against held-out historical actuals
- DuckDB persistence for downstream valuation and report generation
"""
import sys
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

for _site in [
    PROJECT_ROOT / "venv" / "Lib" / "site-packages",
    PROJECT_ROOT / ".venv" / "Lib" / "site-packages",
    PROJECT_ROOT.parent / "venv" / "Lib" / "site-packages",
    PROJECT_ROOT.parent / ".venv" / "Lib" / "site-packages",
]:
    if _site.exists() and str(_site) not in sys.path:
        sys.path.insert(0, str(_site))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

from app.database.connection import db_manager
from app.database.repositories import FinancialFactRepository, ForecastRepository
from app.forecasting.drivers import ForecastDrivers, DriverForecastEngine
from app.forecasting.baselines import BaselineForecastEngine
from app.forecasting.backtest import BacktestMetrics
from app.schemas.modeling import AssumptionSet, ForecastRun
from app.ui.components import load_terminal_theme, render_disclaimer, render_sidebar_company_selector

st.set_page_config(page_title="Forecasting & EDA", page_icon="📈", layout="wide")
load_terminal_theme()

conn = db_manager.get_connection()
company_id, company_name = render_sidebar_company_selector(conn)

fact_repo = FinancialFactRepository(conn)
fc_repo = ForecastRepository(conn)

st.title("📈 Exploratory Analysis & Driver Forecasting")
st.caption("Common-Size Statement Trends, Driver-Based Projections, Baseline Comparisons, and Backtesting")

# Fetch historical facts for the company
facts_df = conn.execute(
    """
    SELECT f.dataset_id, f.dataset_version, f.statement_type, f.canonical_item,
           f.period, f.normalized_value, f.normalized_currency
    FROM financial_facts f
    JOIN datasets d ON f.dataset_id = d.dataset_id
    JOIN dataset_versions v ON f.dataset_id = v.dataset_id AND f.dataset_version = v.version
    WHERE d.company_id = ? AND v.is_active = TRUE
    ORDER BY f.period ASC
    """,
    [company_id],
).fetchdf()

if facts_df.empty:
    entity_disp = company_name if company_name else "an active entity"
    st.warning(f"No financial facts recorded for **{entity_disp}**. Please upload statements on the **Home** dashboard first.")
    render_disclaimer()
    st.stop()

# Pivot facts by period for analysis
pivot_df = facts_df.pivot_table(
    index="period",
    columns="canonical_item",
    values="normalized_value",
    aggfunc="first",
).fillna(0.0)

tab_eda, tab_forecast, tab_baselines = st.tabs([
    "📊 Exploratory Data Analysis & Ratios",
    "🔮 Driver-Based 5-Year Forecast",
    "📐 Baseline Comparisons & Backtesting",
])

# -------------------------------------------------------------
# TAB 1: EXPLORATORY DATA ANALYSIS
# -------------------------------------------------------------
with tab_eda:
    st.subheader(f"Historical Statement Trends & Common-Size Analysis ({company_name})")

    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        st.markdown("##### 📈 Core Income Statement Trend")
        income_items = [c for c in ["revenue", "gross_profit", "operating_income", "net_income"] if c in pivot_df.columns]
        if income_items:
            fig_inc = px.bar(
                facts_df[facts_df["canonical_item"].isin(income_items)],
                x="period",
                y="normalized_value",
                color="canonical_item",
                barmode="group",
                labels={"normalized_value": "Amount ($)", "period": "Period", "canonical_item": "Metric"},
                template="plotly_dark",
            )
            fig_inc.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_inc, use_container_width=True)
        else:
            st.info("No income statement items available.")

    with col_chart2:
        st.markdown("##### 📉 Profitability Margin Trajectory (%)")
        if "revenue" in pivot_df.columns and not pivot_df["revenue"].empty:
            margin_df = pd.DataFrame(index=pivot_df.index)
            rev_series = pivot_df["revenue"].replace(0, np.nan)
            if "gross_profit" in pivot_df.columns:
                margin_df["Gross Margin %"] = (pivot_df["gross_profit"] / rev_series) * 100
            if "operating_income" in pivot_df.columns:
                margin_df["Operating Margin %"] = (pivot_df["operating_income"] / rev_series) * 100
            if "net_income" in pivot_df.columns:
                margin_df["Net Margin %"] = (pivot_df["net_income"] / rev_series) * 100

            fig_margins = px.line(
                margin_df.reset_index(),
                x="period",
                y=margin_df.columns.tolist(),
                markers=True,
                labels={"value": "Margin (%)", "period": "Period", "variable": "Ratio"},
                template="plotly_dark",
            )
            fig_margins.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_margins, use_container_width=True)
        else:
            st.info("Revenue data required for margin trajectory.")

    st.markdown("---")
    st.subheader("📑 Common-Size Income Statement (% of Revenue)")
    if "revenue" in pivot_df.columns and (pivot_df["revenue"] > 0).any():
        common_size_df = pivot_df.copy()
        rev_div = pivot_df["revenue"].replace(0, np.nan)
        for col in common_size_df.columns:
            common_size_df[col] = (common_size_df[col] / rev_div) * 100
        st.dataframe(common_size_df.T.style.format("{:.2f}%"), use_container_width=True)
    else:
        st.info("Common size calculation requires positive revenue.")

# -------------------------------------------------------------
# TAB 2: DRIVER-BASED 5-YEAR PROJECTIONS
# -------------------------------------------------------------
with tab_forecast:
    st.subheader("Operational Drivers & Multi-Period Projections")
    st.caption("Set assumptions below to drive Income Statement, Working Capital, Debt, and Free Cash Flow.")

    # Retrieve base revenue from historical facts
    has_rev = "revenue" in pivot_df.columns and not pivot_df["revenue"].empty
    latest_rev = float(pivot_df["revenue"].iloc[-1]) if has_rev else 100_000_000.0
    latest_debt = float(pivot_df.get("long_term_debt", pd.Series([0.0])).iloc[-1])

    # Load company baseline defaults configured in Settings if available
    b_key = f"company_baseline_{company_id}" if company_id else "global_baseline_defaults"
    b_cfg = st.session_state.get(b_key, st.session_state.get("global_baseline_defaults", {}))

    c_drv1, c_drv2, c_drv3 = st.columns(3)

    with c_drv1:
        st.markdown("**Revenue Growth Assumptions**")
        g1 = st.slider("Year 1 Growth (%)", -20.0, 40.0, float(b_cfg.get("g1", 8.0)), step=0.5) / 100.0
        g2 = st.slider("Year 2 Growth (%)", -20.0, 40.0, float(b_cfg.get("g2", 7.0)), step=0.5) / 100.0
        g3 = st.slider("Year 3 Growth (%)", -20.0, 40.0, float(b_cfg.get("g3", 6.0)), step=0.5) / 100.0
        g4 = st.slider("Year 4 Growth (%)", -20.0, 40.0, float(b_cfg.get("g4", 5.0)), step=0.5) / 100.0
        g5 = st.slider("Year 5 Growth (%)", -20.0, 40.0, float(b_cfg.get("g5", 4.0)), step=0.5) / 100.0

    with c_drv2:
        st.markdown("**Cost & Margin Structure**")
        cogs_pct = st.slider("COGS (% of Revenue)", 20.0, 90.0, float(b_cfg.get("cogs_pct", 58.0)), step=1.0) / 100.0
        opex_pct = st.slider("OpEx (% of Revenue)", 5.0, 50.0, float(b_cfg.get("opex_pct", 15.0)), step=0.5) / 100.0
        tax_pct = st.slider("Corporate Tax Rate (%)", 10.0, 40.0, float(b_cfg.get("tax_rate", 21.0)), step=1.0) / 100.0
        da_pct = st.slider("D&A (% of Revenue)", 1.0, 15.0, float(b_cfg.get("da_pct", 4.0)), step=0.5) / 100.0
        capex_pct = st.slider("CapEx (% of Revenue)", 1.0, 20.0, float(b_cfg.get("capex_pct", 4.5)), step=0.5) / 100.0

    with c_drv3:
        st.markdown("**Working Capital & Debt Drivers**")
        dso = st.slider("DSO (Receivables Days)", 10.0, 120.0, float(b_cfg.get("dso", 45.0)), step=1.0)
        dio = st.slider("DIO (Inventory Days)", 5.0, 120.0, float(b_cfg.get("dio", 35.0)), step=1.0)
        dpo = st.slider("DPO (Payables Days)", 10.0, 120.0, float(b_cfg.get("dpo", 40.0)), step=1.0)
        cost_debt = st.slider("Cost of Debt (%)", 1.0, 15.0, float(b_cfg.get("kd_pretax", 4.5)), step=0.25) / 100.0
        annual_debt_repay = st.number_input("Annual Debt Principal Repayment ($)", value=0.0, step=1_000_000.0)

    drivers = ForecastDrivers(
        revenue_growth_rates=[g1, g2, g3, g4, g5],
        cogs_percent_revenue=cogs_pct,
        opex_percent_revenue=opex_pct,
        tax_rate=tax_pct,
        da_percent_revenue=da_pct,
        capex_percent_revenue=capex_pct,
        days_sales_outstanding=dso,
        days_inventory_outstanding=dio,
        days_payable_outstanding=dpo,
        existing_debt=latest_debt,
        annual_debt_repayment=annual_debt_repay,
        cost_of_debt=cost_debt,
    )

    # Compute Projections
    last_year_label = str(pivot_df.index[-1]) if not pivot_df.empty else "2024"
    try:
        start_yr = int(last_year_label[:4]) + 1
    except Exception:
        start_yr = 2025

    forecast_results = DriverForecastEngine.project_statements(
        base_revenue=latest_rev,
        drivers=drivers,
        start_year=start_yr,
        horizon=5,
        starting_debt=latest_debt,
    )

    st.markdown("---")
    st.subheader("📑 Projected Multi-Year Income & Cash Flow Statement")

    rows = []
    for r in forecast_results:
        rows.append({
            "Period": r.period,
            "Revenue": r.revenue,
            "COGS": r.cogs,
            "Gross Profit": r.gross_profit,
            "Operating Income (EBIT)": r.operating_income,
            "Taxes": r.tax_expense,
            "Net Income": r.net_income,
            "CapEx": r.capex,
            "D&A": r.depreciation_amortization,
            "Change in NWC": r.change_in_nwc,
            "Debt Balance": r.debt_balance,
            "Free Cash Flow (FCF)": r.free_cash_flow,
        })
    df_fc = pd.DataFrame(rows)
    st.dataframe(df_fc.set_index("Period").style.format("${:,.0f}"), use_container_width=True)

    # Plot revenue bridge
    hist_periods = list(pivot_df.index)
    hist_revs = list(pivot_df["revenue"]) if "revenue" in pivot_df.columns else []
    proj_periods = [r.period for r in forecast_results]
    proj_revs = [r.revenue for r in forecast_results]

    chart_periods = hist_periods + proj_periods
    chart_revs = hist_revs + proj_revs
    chart_types = ["Historical"] * len(hist_periods) + ["Projected"] * len(proj_periods)

    fig_fwd = px.bar(
        x=chart_periods,
        y=chart_revs,
        color=chart_types,
        title="Historical & 5-Year Forward Revenue Trajectory",
        labels={"x": "Period", "y": "Revenue ($)", "color": "Series"},
        color_discrete_map={"Historical": "#38BDF8", "Projected": "#10B981"},
        template="plotly_dark",
    )
    fig_fwd.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig_fwd, use_container_width=True)

    # Save to DuckDB Warehouse
    c_save1, c_save2 = st.columns([2, 1])
    with c_save1:
        if st.button("💾 Save Forecast Projections to Warehouse", type="primary", use_container_width=True):
            f_id = f"fc_{uuid.uuid4().hex[:12]}"
            a_id = f"as_{uuid.uuid4().hex[:12]}"

            # Retrieve active dataset id
            ds_id = str(facts_df["dataset_id"].iloc[0])
            ds_ver = int(facts_df["dataset_version"].iloc[0])

            fc_repo.save_assumption_set(
                AssumptionSet(
                    assumption_set_id=a_id,
                    company_id=selected_company,
                    version=1,
                    source="user_input",
                    is_approved=True,
                    assumptions_json=drivers.model_dump(),
                )
            )

            fc_run = ForecastRun(
                forecast_id=f_id,
                dataset_id=ds_id,
                dataset_version=ds_ver,
                assumption_set_id=a_id,
                model_name="driver_based_5yr",
                horizon_periods=5,
                results_json=[r.model_dump() for r in forecast_results],
                backtest_metrics_json={"growth_rates": drivers.revenue_growth_rates},
            )
            fc_repo.save_forecast_run(fc_run)
            st.session_state["active_forecast_id"] = f_id
            st.session_state["active_forecast_results"] = forecast_results
            st.success(f"Successfully saved forecast `{f_id}` to DuckDB! Available in **4_💰_DCF_Valuation**.")

# -------------------------------------------------------------
# TAB 3: BASELINE MODELS & BACKTESTING
# -------------------------------------------------------------
with tab_baselines:
    st.subheader("Statistical Baselines & Backtesting Comparison")
    st.caption("Compares Driver-based forecasting against Naive, Moving Average, and Holt's Linear Exponential Smoothing.")

    if len(hist_revs) < 2:
        st.warning("At least 2 historical periods of revenue are required to run comparative backtesting.")
    else:
        # Evaluate backtest
        eval_metrics = BacktestMetrics.evaluate_model_backtest(
            history=hist_revs,
            holdout_count=1,
            growth_rate=g1,
        )

        if "error" in eval_metrics:
            st.warning(eval_metrics["error"])
        else:
            actual_val = eval_metrics["actuals"][0] if eval_metrics.get("actuals") else 0.0
            driver_m = eval_metrics.get("driver_model", {})
            holt_m = eval_metrics.get("exponential_smoothing", {})
            naive_m = eval_metrics.get("naive", {})

            b_c1, b_c2, b_c3 = st.columns(3)
            b_c1.metric("Actual Held-Out Value", f"${actual_val:,.0f}")
            b_c2.metric("Driver Model MAPE", f"{driver_m.get('mape', 0.0) * 100:.2f}%")
            b_c3.metric("Holt Linear MAPE", f"{holt_m.get('mape', 0.0) * 100:.2f}%")

            st.markdown("##### 📊 Comparative Error Metrics Table")
            comparison_rows = [
                {
                    "Model Architecture": "Driver-Based Model",
                    "Predicted Value ($)": f"${driver_m.get('predictions', [0])[0]:,.0f}",
                    "MAPE (%)": f"{driver_m.get('mape', 0.0) * 100:.2f}%",
                    "RMSE": f"{driver_m.get('rmse', 0.0):,.2f}",
                    "MAE": f"{driver_m.get('mae', 0.0):,.2f}",
                },
                {
                    "Model Architecture": "Holt's Linear Exponential Smoothing",
                    "Predicted Value ($)": f"${holt_m.get('predictions', [0])[0]:,.0f}",
                    "MAPE (%)": f"{holt_m.get('mape', 0.0) * 100:.2f}%",
                    "RMSE": f"{holt_m.get('rmse', 0.0):,.2f}",
                    "MAE": f"{holt_m.get('mae', 0.0):,.2f}",
                },
                {
                    "Model Architecture": "Naive Baseline (Last Value)",
                    "Predicted Value ($)": f"${naive_m.get('predictions', [0])[0]:,.0f}",
                    "MAPE (%)": f"{naive_m.get('mape', 0.0) * 100:.2f}%",
                    "RMSE": f"{naive_m.get('rmse', 0.0):,.2f}",
                    "MAE": f"{naive_m.get('mae', 0.0):,.2f}",
                },
            ]
            st.table(pd.DataFrame(comparison_rows))

render_disclaimer()
