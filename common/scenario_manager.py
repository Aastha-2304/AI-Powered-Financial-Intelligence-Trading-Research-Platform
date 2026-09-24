"""
Scenario Manager for AI Financial Intelligence Platform.
Persists named scenarios (Base / Upside / Downside / Custom) with their
assumptions, and runs the exact same forecast -> working capital ->
cash flow -> DCF pipeline used by report_generator.py and chatbot.py,
so results are always consistent across the whole app.
"""
import os
import sys
import uuid
import json
from pathlib import Path
from datetime import datetime

try:
    from groq import Groq
except ImportError:
    Groq = None

sys.path.append(str(Path(__file__).resolve().parent))
sys.path.append(str(Path(__file__).resolve().parent.parent / "forecasting"))
sys.path.append(str(Path(__file__).resolve().parent.parent / "financial_model"))

from revenue_forecast import (
    get_historical_data,
    derive_default_assumptions,
    project_income_statement,
    get_latest_period_value,
)
from balance_sheet import (
    derive_working_capital_assumptions,
    project_working_capital,
    finalize_balance_sheet,
    get_balancing_items,
)
from cash_flow import project_cash_flow
from dcf import compute_free_cash_flow, run_dcf, estimate_net_debt


def ensure_scenario_schema(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scenarios (
            scenario_id VARCHAR PRIMARY KEY,
            upload_id VARCHAR,
            name VARCHAR,
            scenario_type VARCHAR,
            revenue_growth_rate DOUBLE,
            cogs_pct_revenue DOUBLE,
            opex_pct_revenue DOUBLE,
            tax_rate DOUBLE,
            capex_pct_revenue DOUBLE,
            years_forward INTEGER,
            discount_rate DOUBLE,
            terminal_growth DOUBLE,
            created_at TIMESTAMP
        )
    """)


def preset_assumptions(hist_df, scenario_type: str) -> dict:
    """Base = auto-derived from historical trend. Upside/Downside apply a
    simple, transparent adjustment on top of Base -- easy to explain in
    an interview: 'Upside assumes 50% faster growth and 10% leaner opex
    than the historical trend implies.'"""
    base = derive_default_assumptions(hist_df)

    if scenario_type == "Base":
        return dict(base)

    if scenario_type == "Upside":
        return {
            "revenue_growth_rate": base["revenue_growth_rate"] * 1.5,
            "cogs_pct_revenue": base["cogs_pct_revenue"] * 0.95,
            "opex_pct_revenue": base["opex_pct_revenue"] * 0.90,
            "tax_rate": base["tax_rate"],
            "capex_pct_revenue": base["capex_pct_revenue"],
        }

    if scenario_type == "Downside":
        return {
            "revenue_growth_rate": base["revenue_growth_rate"] * 0.5,
            "cogs_pct_revenue": base["cogs_pct_revenue"] * 1.05,
            "opex_pct_revenue": base["opex_pct_revenue"] * 1.10,
            "tax_rate": base["tax_rate"],
            "capex_pct_revenue": base["capex_pct_revenue"],
        }

    return dict(base)  # Custom starts from Base as a sensible default


def parse_scenario_from_text(hist_df, description: str) -> dict:
    """Parses a plain-English scenario description into the flat
    assumption overrides run_scenario() expects. Any assumption the
    description doesn't mention falls back to the auto-derived baseline
    -- the model is instructed to only override what was actually
    described, never invent unmentioned numbers. Note: assumptions are
    flat rates for the whole projection; a described trajectory (e.g.
    '10% tapering to 6%') gets approximated as a single average rate."""
    if Groq is None:
        raise RuntimeError("The 'groq' package is not installed. Run: pip install groq")
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY environment variable is not set.")

    baseline = preset_assumptions(hist_df, "Base")

    prompt = f"""Parse the scenario description below into a JSON object with exactly these
five keys: revenue_growth_rate, cogs_pct_revenue, opex_pct_revenue, tax_rate, capex_pct_revenue.
All values are decimals (8% = 0.08), representing a single flat rate applied across the whole
projection period.

Baseline (auto-derived from historical trend) -- use these values for ANY assumption the
description does not mention:
{json.dumps(baseline)}

Rules:
- Only change a key if the description actually describes that assumption.
- If the description gives a range or trajectory (e.g. "growing from 10% to 6%"), use the
  AVERAGE of the range as the flat rate.
- "margin of X%" for gross margin means cogs_pct_revenue = 1 - X.
- Output ONLY the JSON object, no explanation, no markdown fences.

Description: "{description}"
"""

    client = Groq(api_key=api_key)
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.choices[0].message.content.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        raise ValueError(f"Could not parse the model's response as JSON: {raw[:200]}")

    result = dict(baseline)
    for key in ("revenue_growth_rate", "cogs_pct_revenue", "opex_pct_revenue", "tax_rate", "capex_pct_revenue"):
        if key in parsed and isinstance(parsed[key], (int, float)):
            result[key] = float(parsed[key])
    return result


def save_scenario(conn, upload_id: str, name: str, scenario_type: str,
                   assumptions: dict, years_forward: int,
                   discount_rate: float, terminal_growth: float) -> str:
    scenario_id = str(uuid.uuid4())
    conn.execute("""
        INSERT INTO scenarios (
            scenario_id, upload_id, name, scenario_type,
            revenue_growth_rate, cogs_pct_revenue, opex_pct_revenue,
            tax_rate, capex_pct_revenue, years_forward,
            discount_rate, terminal_growth, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        scenario_id, upload_id, name, scenario_type,
        assumptions["revenue_growth_rate"], assumptions["cogs_pct_revenue"],
        assumptions["opex_pct_revenue"], assumptions["tax_rate"],
        assumptions["capex_pct_revenue"], years_forward,
        discount_rate, terminal_growth, datetime.now(),
    ])
    return scenario_id


def get_scenarios(conn, upload_id: str):
    return conn.execute("""
        SELECT * FROM scenarios WHERE upload_id = ? ORDER BY created_at DESC
    """, [upload_id]).fetchdf()


def delete_scenario(conn, scenario_id: str):
    conn.execute("DELETE FROM scenarios WHERE scenario_id = ?", [scenario_id])


def run_scenario(conn, upload_id: str, assumptions: dict, years_forward: int,
                  discount_rate: float, terminal_growth: float) -> dict:
    """Runs the full pipeline for one set of assumptions and returns
    income projection, balance sheet, cash flow, and DCF result --
    identical logic to report_generator.gather_report_data(), just
    parameterized instead of hardcoded to one scenario."""
    hist_df = get_historical_data(conn, upload_id)

    income_projection = project_income_statement(hist_df, assumptions, years_forward=years_forward)

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

    fcf_df = compute_free_cash_flow(cash_flow)
    net_debt = estimate_net_debt(hist_df)
    dcf_result = run_dcf(fcf_df, discount_rate, terminal_growth, net_debt)

    return {
        "income_projection": income_projection,
        "balance_sheet": complete_balance_sheet,
        "cash_flow": cash_flow,
        "dcf_result": dcf_result,
    }