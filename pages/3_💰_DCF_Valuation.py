"""
Page 3: Discounted Cash Flow (DCF) Valuation & Sensitivity Engine
AI-Powered Financial Intelligence Platform

Features:
- Deterministic CAPM & WACC calculation (Cost of Equity, After-tax Cost of Debt)
- Multi-period Free Cash Flow discounting: PV = FCF_t / (1 + WACC)^t
- Constant-Growth Gordon Terminal Value: TV = FCF_n * (1 + g) / (WACC - g)
- Mathematical Precondition Guard: Strictly rejects WACC <= g
- Enterprise-to-Equity Value Bridge & Implied Share Price
- Multi-Scenario Engine (Base, Bull, Bear) & Real-time What-If Sliders
- 5x5 Sensitivity Heatmap (WACC vs. Terminal Growth Rate)
- DuckDB persistence for automated report generation
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
from app.database.repositories import ValuationRepository, ForecastRepository, FinancialFactRepository
from app.valuation.wacc import WACCParameters, WACCEngine
from app.valuation.dcf import DCFValuationEngine, DCFGuardError
from app.valuation.scenarios import SensitivityEngine, ScenarioEngine
from app.forecasting.drivers import ForecastDrivers, DriverForecastEngine
from app.schemas.modeling import ValuationRun
from app.ui.components import load_terminal_theme, render_disclaimer, render_sidebar_company_selector

st.set_page_config(page_title="DCF Valuation & Scenarios", page_icon="💰", layout="wide")
load_terminal_theme()

conn = db_manager.get_connection()
company_id, company_name = render_sidebar_company_selector(conn)

val_repo = ValuationRepository(conn)
fc_repo = ForecastRepository(conn)
fact_repo = FinancialFactRepository(conn)

st.title("💰 DCF Valuation & Scenario Intelligence")
st.caption("CAPM/WACC Engine, Multi-Period DCF Bridge, Gordon Terminal Value, and 5x5 Sensitivity Matrix")

# Fetch latest facts to pre-populate balance sheet bridge
facts_df = conn.execute(
    """
    SELECT f.canonical_item, f.normalized_value, f.dataset_id, f.dataset_version
    FROM financial_facts f
    JOIN datasets d ON f.dataset_id = d.dataset_id
    JOIN dataset_versions v ON f.dataset_id = v.dataset_id AND f.dataset_version = v.version
    WHERE d.company_id = ? AND v.is_active = TRUE
    ORDER BY f.period DESC
    """,
    [company_id],
).fetchdf()

# Defaults from database facts
default_debt = 0.0
default_cash = 0.0
active_dataset_id = "ds_default"
active_dataset_ver = 1

if not facts_df.empty:
    active_dataset_id = str(facts_df["dataset_id"].iloc[0])
    active_dataset_ver = int(facts_df["dataset_version"].iloc[0])
    debt_match = facts_df[facts_df["canonical_item"].isin(["long_term_debt", "total_debt"])]
    if not debt_match.empty:
        default_debt = float(debt_match["normalized_value"].iloc[0])
    cash_match = facts_df[facts_df["canonical_item"].isin(["cash_and_equivalents"])]
    if not cash_match.empty:
        default_cash = float(cash_match["normalized_value"].iloc[0])

# Retrieve active forecast if available in session or database
latest_fc = conn.execute(
    """
    SELECT forecast_id, results_json, assumption_set_id FROM forecast_runs
    WHERE dataset_id LIKE ? ORDER BY created_at DESC LIMIT 1
    """,
    [f"%{company_id}%"]
).fetchone()

default_fcfs = [85_000_000.0, 92_000_000.0, 101_000_000.0, 110_000_000.0, 120_000_000.0]
default_periods = ["2025", "2026", "2027", "2028", "2029"]
active_fc_id = None
active_assumption_id = None

if latest_fc:
    import json
    active_fc_id = latest_fc[0]
    active_assumption_id = latest_fc[2]
    fc_results = json.loads(latest_fc[1])
    default_fcfs = [float(p.get("free_cash_flow", 100_000_000)) for p in fc_results]
    default_periods = [str(p.get("period", f"Y{i+1}")) for i, p in enumerate(fc_results)]

tab_dcf, tab_scenarios, tab_sens = st.tabs([
    "💵 Discounted Cash Flow Bridge",
    "🎭 Multi-Scenario & What-If Analysis",
    "🌡️ 5x5 Sensitivity Matrix",
])

# -------------------------------------------------------------
# TAB 1: DCF BRIDGE & WACC ENGINE
# -------------------------------------------------------------
with tab_dcf:
    st.subheader("1. Cost of Capital (CAPM & WACC Engine)")

    # Read company baseline configuration from Settings if available
    b_key = f"company_baseline_{company_id}" if company_id else "global_baseline_defaults"
    b_cfg = st.session_state.get(b_key, st.session_state.get("global_baseline_defaults", {}))

    col_capm1, col_capm2, col_capm3 = st.columns(3)

    with col_capm1:
        st.markdown("**Cost of Equity ($K_e$) via CAPM**")
        rf = st.number_input("Risk-Free Rate ($R_f$) %", value=float(b_cfg.get("rf", 4.2)), step=0.1) / 100.0
        beta = st.number_input("Equity Beta ($\beta$)", value=float(b_cfg.get("beta", 1.15)), step=0.05)
        erp = st.number_input("Equity Risk Premium (ERP) %", value=float(b_cfg.get("erp", 5.5)), step=0.1) / 100.0
        ke = rf + (beta * erp)
        st.caption(f"Calculated Cost of Equity: **{ke*100:.2f}%**")

    with col_capm2:
        st.markdown("**Cost of Debt ($K_d$)**")
        kd_pretax = st.number_input("Pre-Tax Borrowing Rate ($K_d$) %", value=float(b_cfg.get("kd_pretax", 4.75)), step=0.25) / 100.0
        tax_rate = st.number_input("Marginal Tax Rate ($t$) %", value=float(b_cfg.get("tax_rate", 21.0)), step=1.0) / 100.0
        kd_after_tax = kd_pretax * (1.0 - tax_rate)
        st.caption(f"After-Tax Cost of Debt: **{kd_after_tax*100:.2f}%**")

    with col_capm3:
        st.markdown("**Capital Structure Weights**")
        eq_pct = st.slider("Target Equity Weight (E / V) %", 10.0, 100.0, float(b_cfg.get("eq_weight", 80.0)), step=5.0) / 100.0
        debt_pct = 1.0 - eq_pct
        st.caption(f"Debt Weight (D / V): **{debt_pct*100:.1f}%**")

        wacc_params = WACCParameters(
            risk_free_rate=rf,
            beta=beta,
            equity_risk_premium=erp,
            cost_of_debt_pretax=kd_pretax,
            tax_rate=tax_rate,
            equity_weight=eq_pct,
            debt_weight=debt_pct,
        )
        wacc_res = WACCEngine.calculate_wacc(wacc_params)
        wacc = wacc_res.wacc
        st.metric("Blended WACC (Discount Rate)", f"{wacc*100:.2f}%")

    st.markdown("---")
    st.subheader("2. Terminal Value & Enterprise-to-Equity Bridge")

    col_tv1, col_tv2 = st.columns(2)
    with col_tv1:
        g_rate = st.number_input("Perpetual Terminal Growth Rate ($g$) %", value=float(b_cfg.get("terminal_growth", 2.5)), step=0.1) / 100.0
        total_debt_val = st.number_input("Total Debt ($)", value=float(default_debt), step=1_000_000.0)
        cash_val = st.number_input("Cash & Cash Equivalents ($)", value=float(default_cash), step=1_000_000.0)
        shares_out = st.number_input("Shares Outstanding (Units)", value=15_500_000_000.0, step=100_000_000.0)

    with col_tv2:
        st.markdown("**Non-Negotiable Mathematical Precondition Guard**")
        if wacc <= g_rate:
            st.error(f"🚨 **FATAL PRECONDITION VIOLATION**: WACC ({wacc*100:.2f}%) must be strictly greater than Terminal Growth Rate ($g$ = {g_rate*100:.2f}%). Gordon Growth model diverges.")
            st.stop()
        else:
            spread = (wacc - g_rate) * 100
            st.success(f"✅ Guard Verified: $WACC - g$ spread is **+{spread:.2f}%** (Well-conditioned)")

    # Execute DCF
    try:
        dcf_result = DCFValuationEngine.calculate_dcf(
            forecast_fcfs=default_fcfs,
            forecast_periods=default_periods,
            wacc=wacc,
            terminal_growth_rate=g_rate,
            total_debt=total_debt_val,
            cash_and_equivalents=cash_val,
            shares_outstanding=shares_out,
        )
    except DCFGuardError as e:
        st.error(f"Valuation error: {str(e)}")
        st.stop()

    # Metrics Display
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Enterprise Value (EV)", f"${dcf_result.enterprise_value:,.0f}")
    m2.metric("Equity Value", f"${dcf_result.equity_value:,.0f}")
    m3.metric("Terminal Value (PV)", f"${dcf_result.pv_terminal_value:,.0f}")
    m4.metric("Implied Share Price", f"${dcf_result.implied_share_price:.2f}" if dcf_result.implied_share_price else "N/A")

    # Discounted Cash Flow Breakdown Table
    st.markdown("##### 📑 Multi-Period Discounted Cash Flow Schedule")
    dcf_table_rows = []
    for t_idx, (p_label, fcf_val, factor, pv_fcf) in enumerate(zip(
        dcf_result.forecast_periods,
        dcf_result.forecast_fcfs,
        dcf_result.discount_factors,
        dcf_result.pv_forecast_fcfs,
    )):
        dcf_table_rows.append({
            "Period": p_label,
            "Year Index (t)": t_idx + 1,
            "Undiscounted FCF ($)": fcf_val,
            "Discount Factor [1/(1+WACC)^t]": factor,
            "Present Value (PV) ($)": pv_fcf,
        })
    df_dcf = pd.DataFrame(dcf_table_rows)
    st.dataframe(df_dcf.style.format({
        "Undiscounted FCF ($)": "${:,.0f}",
        "Discount Factor [1/(1+WACC)^t]": "{:.4f}",
        "Present Value (PV) ($)": "${:,.0f}",
    }), use_container_width=True)

    # Waterfall Bridge
    bridge_labels = ["Sum PV of FCFs", "PV of Terminal Value", "Enterprise Value", "Less Debt", "Plus Cash", "Equity Value"]
    bridge_vals = [
        dcf_result.sum_pv_fcfs,
        dcf_result.pv_terminal_value,
        dcf_result.enterprise_value,
        -total_debt_val,
        cash_val,
        dcf_result.equity_value,
    ]
    fig_bridge = go.Figure(go.Waterfall(
        name="Valuation Bridge",
        orientation="v",
        measure=["relative", "relative", "total", "relative", "relative", "total"],
        x=bridge_labels,
        y=bridge_vals,
        connector={"line": {"color": "#64748B"}},
        decreasing={"marker": {"color": "#EF4444"}},
        increasing={"marker": {"color": "#10B981"}},
        totals={"marker": {"color": "#38BDF8"}},
    ))
    fig_bridge.update_layout(
        title="Enterprise-to-Equity Value Bridge Waterfall",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#F8FAFC",
        height=380,
    )
    st.plotly_chart(fig_bridge, use_container_width=True)

    # Save to warehouse button
    if st.button("💾 Save DCF Valuation Run to DuckDB Warehouse", type="primary", use_container_width=True):
        if not active_fc_id:
            st.error("Please run and save a forecast in 2_📈_Forecasting before saving valuation.")
        else:
            val_id = f"val_{uuid.uuid4().hex[:12]}"
            val_run = ValuationRun(
                valuation_id=val_id,
                dataset_id=active_dataset_id,
                dataset_version=active_dataset_ver,
                forecast_id=active_fc_id,
                assumption_set_id=active_assumption_id or "as_default",
                wacc=wacc,
                terminal_growth_rate=g_rate,
                enterprise_value=dcf_result.enterprise_value,
                equity_value=dcf_result.equity_value,
                implied_share_price=dcf_result.implied_share_price,
                sensitivity_grid_json={},
                scenarios_json={},
            )
            val_repo.save_valuation_run(val_run)
            st.session_state["active_valuation_id"] = val_id
            st.success(f"Valuation `{val_id}` successfully committed to DuckDB! Available in **5_📑_Reports**.")

# -------------------------------------------------------------
# TAB 2: MULTI-SCENARIO & WHAT-IF ANALYSIS
# -------------------------------------------------------------
with tab_scenarios:
    st.subheader("Base, Bull, and Bear Operational Scenarios")
    st.caption("Evaluates optimistic expansion (+3% revenue, +2% margin, -0.5% WACC) vs. conservative compression.")

    base_drivers = ForecastDrivers(
        revenue_growth_rates=[0.08, 0.07, 0.06, 0.05, 0.04],
        cogs_percent_revenue=0.58,
        existing_debt=total_debt_val,
    )

    base_rev_val = default_fcfs[0] / 0.15  # normalized baseline proxy
    scenario_res = ScenarioEngine.run_scenarios(
        base_revenue=base_rev_val,
        base_drivers=base_drivers,
        base_wacc=wacc,
        base_terminal_growth=g_rate,
        total_debt=total_debt_val,
        cash_and_equivalents=cash_val,
        shares_outstanding=shares_out,
    )

    sc_col1, sc_col2, sc_col3 = st.columns(3)
    with sc_col1:
        st.markdown("#### 🐻 Bear Case")
        bear_data = scenario_res["bear"]
        st.metric("Enterprise Value", f"${bear_data['enterprise_value']:,.0f}")
        st.metric("Implied Share Price", f"${bear_data['implied_share_price']:.2f}")
        st.caption(f"WACC: {bear_data['wacc']*100:.2f}% | g: {bear_data['terminal_growth']*100:.2f}%")

    with sc_col2:
        st.markdown("#### ⚖️ Base Case")
        base_data = scenario_res["base"]
        st.metric("Enterprise Value", f"${base_data['enterprise_value']:,.0f}")
        st.metric("Implied Share Price", f"${base_data['implied_share_price']:.2f}")
        st.caption(f"WACC: {base_data['wacc']*100:.2f}% | g: {base_data['terminal_growth']*100:.2f}%")

    with sc_col3:
        st.markdown("#### 🐂 Bull Case")
        bull_data = scenario_res["bull"]
        st.metric("Enterprise Value", f"${bull_data['enterprise_value']:,.0f}")
        st.metric("Implied Share Price", f"${bull_data['implied_share_price']:.2f}")
        st.caption(f"WACC: {bull_data['wacc']*100:.2f}% | g: {bull_data['terminal_growth']*100:.2f}%")

    # Comparison Bar Chart
    sc_df = pd.DataFrame([
        {"Scenario": "Bear Case", "Implied Share Price": bear_data["implied_share_price"], "EV": bear_data["enterprise_value"]},
        {"Scenario": "Base Case", "Implied Share Price": base_data["implied_share_price"], "EV": base_data["enterprise_value"]},
        {"Scenario": "Bull Case", "Implied Share Price": bull_data["implied_share_price"], "EV": bull_data["enterprise_value"]},
    ])
    fig_sc = px.bar(
        sc_df,
        x="Scenario",
        y="Implied Share Price",
        color="Scenario",
        title="Multi-Scenario Implied Share Price Comparison ($ / Share)",
        color_discrete_map={"Bear Case": "#EF4444", "Base Case": "#38BDF8", "Bull Case": "#10B981"},
        template="plotly_dark",
    )
    fig_sc.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig_sc, use_container_width=True)

# -------------------------------------------------------------
# TAB 3: 5x5 SENSITIVITY MATRIX
# -------------------------------------------------------------
with tab_sens:
    st.subheader("5x5 Sensitivity Analysis Matrix")
    st.caption("Evaluates valuation resilience against simultaneous shifts in WACC (rows) and Terminal Growth Rate (columns).")

    sens_data = SensitivityEngine.generate_wacc_growth_matrix(
        forecast_fcfs=default_fcfs,
        forecast_periods=default_periods,
        base_wacc=wacc,
        base_terminal_growth=g_rate,
        total_debt=total_debt_val,
        cash_and_equivalents=cash_val,
        shares_outstanding=shares_out,
    )

    wacc_labels = [f"{w*100:.2f}%" for w in sens_data["wacc_axis"]]
    growth_labels = [f"{g*100:.2f}%" for g in sens_data["growth_axis"]]

    matrix_type = st.radio("Display Sensitivity Metric", ["Implied Share Price ($)", "Enterprise Value ($M)"], horizontal=True)

    if "Share Price" in matrix_type:
        matrix_grid = sens_data["share_price_matrix"]
        val_fmt = "${:.2f}"
    else:
        # Scale to millions
        matrix_grid = [
            [(v / 1_000_000.0 if v is not None else np.nan) for v in row]
            for row in sens_data["enterprise_value_matrix"]
        ]
        val_fmt = "${:,.0f}M"

    df_sens = pd.DataFrame(matrix_grid, index=wacc_labels, columns=growth_labels)
    st.dataframe(df_sens.style.format(val_fmt, na_rep="INVALID (WACC<=g)"), use_container_width=True)

    # Plotly Heatmap
    z_vals = [[(v if v is not None else np.nan) for v in row] for row in matrix_grid]
    fig_heat = px.imshow(
        z_vals,
        x=growth_labels,
        y=wacc_labels,
        labels=dict(x="Terminal Growth Rate (g)", y="WACC (Discount Rate)", color=matrix_type),
        color_continuous_scale="Viridis",
        title="Valuation Sensitivity Heatmap",
        template="plotly_dark",
    )
    fig_heat.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig_heat, use_container_width=True)

render_disclaimer()
