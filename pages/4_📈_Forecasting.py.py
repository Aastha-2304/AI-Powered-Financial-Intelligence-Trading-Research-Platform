"""
Forecasting -- assumptions, projections, and DCF valuation
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent))
sys.path.append(str(Path(__file__).resolve().parent.parent / "common"))
sys.path.append(str(Path(__file__).resolve().parent.parent / "forecasting"))
sys.path.append(str(Path(__file__).resolve().parent.parent / "financial_model"))

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

from shared_utils import get_connection, render_upload_selector
from revenue_forecast import get_historical_data, derive_default_assumptions, project_income_statement, get_latest_period_value
from balance_sheet import derive_working_capital_assumptions, project_working_capital, finalize_balance_sheet, get_balancing_items
from cash_flow import project_cash_flow
from dcf import compute_free_cash_flow, run_dcf, estimate_net_debt
from styles import load_custom_css, gradient_header, powerbi_kpi
from chart_theme import apply_theme, area_line_chart
from sensitivity import compute_dcf_sensitivity_grid

st.set_page_config(page_title="Forecasting", layout="wide")
load_custom_css()
gradient_header("Financial Forecasting & Valuation", "Adjustable assumptions, projected statements, and DCF valuation")

conn = get_connection()
upload_id, company_name = render_upload_selector(conn)

st.divider()

hist_df = get_historical_data(conn, upload_id)
if hist_df.empty:
    st.warning(f"No historical data found for {company_name}.")
    st.stop()

# ---------------------------------------------------------------------
# 1. Assumptions (auto-derived, user-overridable)
# ---------------------------------------------------------------------
st.subheader("1. Assumptions")
st.caption("Auto-calculated from historical trend -- adjust any value to see the projection update.")

default_income_assumptions = derive_default_assumptions(hist_df)

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    revenue_growth_rate = st.number_input(
        "Revenue Growth Rate (%)", value=round(default_income_assumptions["revenue_growth_rate"] * 100, 2),
        step=0.5, format="%.2f") / 100
with col2:
    cogs_pct_revenue = st.number_input(
        "COGS (% of Revenue)", value=round(default_income_assumptions["cogs_pct_revenue"] * 100, 2),
        step=0.5, format="%.2f") / 100
with col3:
    opex_pct_revenue = st.number_input(
        "Opex (% of Revenue)", value=round(default_income_assumptions["opex_pct_revenue"] * 100, 2),
        step=0.5, format="%.2f") / 100
with col4:
    tax_rate = st.number_input(
        "Tax Rate (%)", value=round(default_income_assumptions["tax_rate"] * 100, 2),
        step=0.5, format="%.2f") / 100
with col5:
    capex_pct_revenue = st.number_input(
        "Capex (% of Revenue)", value=round(default_income_assumptions["capex_pct_revenue"] * 100, 2),
        step=0.5, format="%.2f") / 100

income_assumptions = {
    "revenue_growth_rate": revenue_growth_rate,
    "cogs_pct_revenue": cogs_pct_revenue,
    "opex_pct_revenue": opex_pct_revenue,
    "tax_rate": tax_rate,
    "capex_pct_revenue": capex_pct_revenue,
}

years_forward = st.slider("Years to project", min_value=1, max_value=10, value=5)

st.divider()

# ---------------------------------------------------------------------
# 2. Run the linked 3-statement projection
# ---------------------------------------------------------------------
income_projection = project_income_statement(hist_df, income_assumptions, years_forward=years_forward)

wc_assumptions = derive_working_capital_assumptions(hist_df)
starting_total_assets = get_latest_period_value(hist_df, "total_assets") or 0.0
starting_current_assets = get_latest_period_value(hist_df, "total_current_assets") or 0.0
starting_non_current_assets = starting_total_assets - starting_current_assets
balancing_items = get_balancing_items(hist_df)

working_capital = project_working_capital(
    income_projection, hist_df, wc_assumptions, starting_non_current_assets, balancing_items
)

starting_cash = get_latest_period_value(hist_df, "cash_and_equivalents") or 0.0
starting_ar = get_latest_period_value(hist_df, "accounts_receivable") or 0.0
starting_inventory = get_latest_period_value(hist_df, "inventory") or 0.0
starting_ap = get_latest_period_value(hist_df, "accounts_payable") or 0.0
starting_current_liab = get_latest_period_value(hist_df, "total_current_liabilities") or 0.0
starting_other_liab = starting_current_liab - starting_ap

cash_flow = project_cash_flow(
    income_projection, working_capital, starting_cash,
    starting_ar=starting_ar, starting_inventory=starting_inventory,
    starting_ap=starting_ap, starting_other_liab=starting_other_liab,
)

complete_balance_sheet = finalize_balance_sheet(working_capital, cash_flow)

st.subheader("2. Projected Financials")
tab1, tab2, tab3 = st.tabs(["Income Statement", "Balance Sheet", "Cash Flow"])

with tab1:
    fig = area_line_chart(income_projection, x="period", y=["revenue", "gross_profit", "net_income"])
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(income_projection, use_container_width=True, hide_index=True)

with tab2:
    fig = area_line_chart(complete_balance_sheet, x="period", y=["total_assets", "total_liabilities", "total_equity"])
    st.plotly_chart(fig, use_container_width=True)

    all_balanced = complete_balance_sheet["balances"].all()
    if all_balanced:
        st.success("Balance sheet balances in every projected period (Assets = Liabilities + Equity).")
    else:
        st.error("Balance sheet does not balance in one or more periods -- check assumptions.")
    st.dataframe(complete_balance_sheet, use_container_width=True, hide_index=True)

with tab3:
    fig = px.bar(cash_flow, x="period", y="net_change_in_cash")
    fig.add_scatter(x=cash_flow["period"], y=cash_flow["ending_cash"], mode="lines+markers", name="Ending Cash", yaxis="y2")
    st.plotly_chart(apply_theme(fig), use_container_width=True)
    st.dataframe(cash_flow, use_container_width=True, hide_index=True)

st.divider()

# ---------------------------------------------------------------------
# 3. DCF Valuation
# ---------------------------------------------------------------------
st.subheader("3. DCF Valuation")

col1, col2 = st.columns(2)
with col1:
    discount_rate = st.slider("Discount Rate / WACC (%)", min_value=4.0, max_value=20.0, value=10.0, step=0.5) / 100
with col2:
    terminal_growth_rate = st.slider("Terminal Growth Rate (%)", min_value=0.0, max_value=6.0, value=2.5, step=0.25) / 100

fcf_df = compute_free_cash_flow(cash_flow)
net_debt = estimate_net_debt(hist_df)

try:
    result = run_dcf(fcf_df, discount_rate, terminal_growth_rate, net_debt)

    col1, col2, col3 = st.columns(3)
    with col1: powerbi_kpi("Enterprise Value", f"${result['enterprise_value']:,.0f}")
    with col2: powerbi_kpi("Net Debt", f"${result['net_debt']:,.0f}")
    with col3: powerbi_kpi("Implied Equity Value", f"${result['equity_value']:,.0f}")

    fig = go.Figure()
    fig.add_bar(x=result["detail"]["period"], y=result["detail"]["discounted_fcf"], name="Discounted FCF")
    fig.update_layout(title="Discounted Free Cash Flow by Year", yaxis_title="USD")
    st.plotly_chart(apply_theme(fig), use_container_width=True)

    with st.expander("See full DCF detail"):
        st.dataframe(result["detail"][["period", "free_cash_flow", "discounted_fcf"]], use_container_width=True, hide_index=True)
        st.write(f"Sum of Discounted FCFs: ${result['sum_discounted_fcf']:,.2f}")
        st.write(f"Terminal Value: ${result['terminal_value']:,.2f}")
        st.write(f"Discounted Terminal Value: ${result['discounted_terminal_value']:,.2f}")

    st.divider()
    st.subheader("4. DCF Sensitivity Table")
    st.caption("Enterprise Value across a grid of discount rate and terminal growth combinations -- shows how sensitive the valuation is to your assumptions.")

    value_choice = st.radio("Show", ["Enterprise Value", "Equity Value"], horizontal=True)
    value_key = "enterprise_value" if value_choice == "Enterprise Value" else "equity_value"

    sensitivity_grid = compute_dcf_sensitivity_grid(fcf_df, net_debt, run_dcf, value_key=value_key)

    display_grid = sensitivity_grid.copy()
    display_grid.index = [f"{r:.1%}" for r in display_grid.index]
    display_grid.columns = [f"{c:.1%}" for c in display_grid.columns]

    fig_sens = go.Figure(data=go.Heatmap(
        z=sensitivity_grid.values,
        x=[f"{c:.1%}" for c in sensitivity_grid.columns],
        y=[f"{r:.1%}" for r in sensitivity_grid.index],
        colorscale=[[0, "#F87171"], [0.5, "#FBBF24"], [1, "#34D399"]],
        text=[[f"${v:,.0f}" if v is not None else "" for v in row] for row in sensitivity_grid.values],
        texttemplate="%{text}",
        textfont={"size": 11},
        hovertemplate="Discount Rate: %{y}<br>Terminal Growth: %{x}<br>Value: %{z:$,.0f}<extra></extra>",
    ))
    fig_sens.update_layout(
        xaxis_title="Terminal Growth Rate", yaxis_title="Discount Rate (WACC)",
        height=400,
    )
    st.plotly_chart(apply_theme(fig_sens), use_container_width=True)
    st.caption("Blank cells mean terminal growth exceeded the discount rate, which breaks the perpetuity formula -- not a valid combination.")

except ValueError as e:
    st.error(str(e))