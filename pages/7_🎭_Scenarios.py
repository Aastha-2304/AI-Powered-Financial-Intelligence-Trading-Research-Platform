"""
Scenario Manager -- create, save, and compare Base/Upside/Downside/Custom scenarios
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent))
sys.path.append(str(Path(__file__).resolve().parent.parent / "common"))
sys.path.append(str(Path(__file__).resolve().parent.parent / "ai_agent"))

import streamlit as st
import pandas as pd

from shared_utils import get_connection, render_upload_selector
from styles import load_custom_css, gradient_header, powerbi_kpi
from chart_theme import apply_theme, area_line_chart, colored_bar_chart
from scenario_manager import (
    ensure_scenario_schema, preset_assumptions, save_scenario,
    parse_scenario_from_text,
    get_scenarios, delete_scenario, run_scenario,
)
from revenue_forecast import get_historical_data

st.set_page_config(page_title="Scenario Manager", layout="wide")
load_custom_css()
gradient_header("Scenario Manager", "Create, save, and compare Base / Upside / Downside forecasts")

conn = get_connection()
ensure_scenario_schema(conn)
upload_id, company_name = render_upload_selector(conn)

hist_df = get_historical_data(conn, upload_id)
if hist_df.empty:
    st.warning(f"No historical data found for {company_name}.")
    st.stop()

st.divider()

# ---------------------------------------------------------------------
# Quick-create presets
# ---------------------------------------------------------------------
st.subheader("1. Create a scenario")

preset_cols = st.columns(3)
preset_types = ["Base", "Upside", "Downside"]
for col, ptype in zip(preset_cols, preset_types):
    with col:
        if st.button(f"Generate {ptype}", use_container_width=True):
            assumptions = preset_assumptions(hist_df, ptype)
            save_scenario(conn, upload_id, f"{ptype} ({pd.Timestamp.now().strftime('%H:%M:%S')})",
                          ptype, assumptions, years_forward=5, discount_rate=0.10, terminal_growth=0.025)
            st.success(f"{ptype} scenario saved.")
            st.rerun()

with st.expander("Or describe it in plain English"):
    st.caption(
        "e.g. \"Assume 8% revenue growth with margins improving to 42% gross margin\" -- "
        "anything you don't mention falls back to the auto-derived baseline. Note: this "
        "applies one flat rate across all years; it can't represent a rate that changes "
        "year to year."
    )
    nl_name = st.text_input("Scenario name", value="NL Scenario", key="nl_name")
    nl_description = st.text_area(
        "Describe the scenario", placeholder="Assume 10% revenue growth and opex held at 20% of revenue...",
        key="nl_description",
    )
    if st.button("Parse & Save", key="nl_parse_button"):
        if not nl_description.strip():
            st.warning("Enter a description first.")
        else:
            try:
                with st.spinner("Parsing description..."):
                    nl_assumptions = parse_scenario_from_text(hist_df, nl_description)
                st.success("Parsed assumptions:")
                st.json(nl_assumptions)
                save_scenario(conn, upload_id, nl_name, "Custom", nl_assumptions,
                              years_forward=5, discount_rate=0.10, terminal_growth=0.025)
                st.success(f"'{nl_name}' saved.")
                st.rerun()
            except Exception as e:
                st.error(f"Couldn't parse that description: {e}")

with st.expander("Or build a custom scenario"):
    base = preset_assumptions(hist_df, "Base")
    custom_name = st.text_input("Scenario name", value="My Custom Scenario")

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        rev_growth = st.number_input("Revenue Growth (%)", value=round(base["revenue_growth_rate"] * 100, 2)) / 100
    with c2:
        cogs = st.number_input("COGS (% Rev)", value=round(base["cogs_pct_revenue"] * 100, 2)) / 100
    with c3:
        opex = st.number_input("Opex (% Rev)", value=round(base["opex_pct_revenue"] * 100, 2)) / 100
    with c4:
        tax = st.number_input("Tax Rate (%)", value=round(base["tax_rate"] * 100, 2)) / 100
    with c5:
        capex = st.number_input("Capex (% Rev)", value=round(base["capex_pct_revenue"] * 100, 2)) / 100

    c6, c7, c8 = st.columns(3)
    with c6:
        custom_years = st.slider("Years forward", 1, 10, 5, key="custom_years")
    with c7:
        custom_discount = st.slider("Discount rate (%)", 4.0, 20.0, 10.0, 0.5, key="custom_discount") / 100
    with c8:
        custom_terminal = st.slider("Terminal growth (%)", 0.0, 6.0, 2.5, 0.25, key="custom_terminal") / 100

    if st.button("Save Custom Scenario", type="primary"):
        custom_assumptions = {
            "revenue_growth_rate": rev_growth, "cogs_pct_revenue": cogs,
            "opex_pct_revenue": opex, "tax_rate": tax, "capex_pct_revenue": capex,
        }
        save_scenario(conn, upload_id, custom_name, "Custom", custom_assumptions,
                      custom_years, custom_discount, custom_terminal)
        st.success(f"'{custom_name}' saved.")
        st.rerun()

st.divider()

# ---------------------------------------------------------------------
# Saved scenarios + comparison
# ---------------------------------------------------------------------
st.subheader("2. Compare scenarios")

scenarios = get_scenarios(conn, upload_id)
if scenarios.empty:
    st.info("No scenarios saved yet -- create one above to get started.")
    st.stop()

selected_names = st.multiselect(
    "Select scenarios to compare", options=scenarios["name"].tolist(),
    default=scenarios["name"].tolist()[:3],
)

if selected_names:
    results = {}
    for _, row in scenarios[scenarios["name"].isin(selected_names)].iterrows():
        assumptions = {
            "revenue_growth_rate": row["revenue_growth_rate"],
            "cogs_pct_revenue": row["cogs_pct_revenue"],
            "opex_pct_revenue": row["opex_pct_revenue"],
            "tax_rate": row["tax_rate"],
            "capex_pct_revenue": row["capex_pct_revenue"],
        }
        results[row["name"]] = run_scenario(
            conn, upload_id, assumptions, int(row["years_forward"]),
            row["discount_rate"], row["terminal_growth"],
        )

    # KPI row -- implied equity value per scenario
    kpi_cols = st.columns(len(results))
    for col, (name, res) in zip(kpi_cols, results.items()):
        with col:
            powerbi_kpi(name, f"${res['dcf_result']['equity_value']:,.0f}")

    st.markdown("#### Net income projection by scenario")
    combined = []
    for name, res in results.items():
        df = res["income_projection"][["period", "net_income"]].copy()
        df["scenario"] = name
        combined.append(df)
    combined_df = pd.concat(combined, ignore_index=True)

    import plotly.express as px
    fig = px.line(combined_df, x="period", y="net_income", color="scenario", markers=True)
    st.plotly_chart(apply_theme(fig), use_container_width=True)

    st.markdown("#### Implied equity value by scenario")
    equity_df = pd.DataFrame({
        "scenario": list(results.keys()),
        "equity_value": [res["dcf_result"]["equity_value"] for res in results.values()],
    })
    fig2 = colored_bar_chart(equity_df, x="scenario", y="equity_value", title="")
    st.plotly_chart(fig2, use_container_width=True)

st.divider()

# ---------------------------------------------------------------------
# Manage saved scenarios
# ---------------------------------------------------------------------
st.subheader("3. Saved scenarios")
display_cols = ["name", "scenario_type", "revenue_growth_rate", "cogs_pct_revenue",
                 "opex_pct_revenue", "tax_rate", "capex_pct_revenue", "created_at"]
st.dataframe(scenarios[display_cols], use_container_width=True, hide_index=True)

del_choice = st.selectbox("Delete a scenario", ["-- select --"] + scenarios["name"].tolist())
if del_choice != "-- select --" and st.button("Delete Selected Scenario"):
    scenario_id = scenarios[scenarios["name"] == del_choice]["scenario_id"].iloc[0]
    delete_scenario(conn, scenario_id)
    st.success(f"Deleted '{del_choice}'.")
    st.rerun()