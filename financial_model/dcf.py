"""
DCF Valuation module for AI Financial Intelligence Platform
Discounts projected free cash flows back to present value to estimate
an implied enterprise/equity valuation.
"""
import sys
from pathlib import Path
import duckdb
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

sys.path.append(str(Path(__file__).resolve().parent.parent))
from config import DB_PATH


def compute_free_cash_flow(cash_flow: pd.DataFrame) -> pd.DataFrame:
    """
    Unlevered Free Cash Flow = Cash from Operations - Capex.
    (We're using operating cash flow as a proxy since we don't model
    interest/tax-shield adjustments separately -- a reasonable
    simplification for a first-pass DCF.)
    """
    fcf = cash_flow[["period", "cash_from_operations", "capital_expenditures"]].copy()
    fcf["free_cash_flow"] = fcf["cash_from_operations"] + fcf["capital_expenditures"]  # capex already negative
    return fcf


def compute_terminal_value(final_year_fcf: float, terminal_growth_rate: float, discount_rate: float) -> float:
    """
    Gordon Growth terminal value: FCF in the year after the explicit
    forecast, divided by (discount rate - terminal growth rate).
    Assumes discount_rate > terminal_growth_rate (checked below).
    """
    if discount_rate <= terminal_growth_rate:
        raise ValueError("Discount rate must exceed terminal growth rate for a valid terminal value.")
    next_year_fcf = final_year_fcf * (1 + terminal_growth_rate)
    return next_year_fcf / (discount_rate - terminal_growth_rate)


def run_dcf(fcf_df: pd.DataFrame, discount_rate: float, terminal_growth_rate: float,
            net_debt: float = 0.0) -> dict:
    """
    Discounts each projected year's FCF back to present value, adds a
    discounted terminal value, and derives implied enterprise and
    equity value.
    """
    years = list(range(1, len(fcf_df) + 1))
    fcf_values = fcf_df["free_cash_flow"].tolist()

    discounted_fcfs = []
    for year, fcf in zip(years, fcf_values):
        pv = fcf / ((1 + discount_rate) ** year)
        discounted_fcfs.append(pv)

    terminal_value = compute_terminal_value(fcf_values[-1], terminal_growth_rate, discount_rate)
    discounted_terminal_value = terminal_value / ((1 + discount_rate) ** years[-1])

    enterprise_value = sum(discounted_fcfs) + discounted_terminal_value
    equity_value = enterprise_value - net_debt

    detail = fcf_df.copy()
    detail["year"] = years
    detail["discounted_fcf"] = [round(v, 2) for v in discounted_fcfs]

    return {
        "detail": detail,
        "sum_discounted_fcf": round(sum(discounted_fcfs), 2),
        "terminal_value": round(terminal_value, 2),
        "discounted_terminal_value": round(discounted_terminal_value, 2),
        "enterprise_value": round(enterprise_value, 2),
        "net_debt": round(net_debt, 2),
        "equity_value": round(equity_value, 2),
        "discount_rate": discount_rate,
        "terminal_growth_rate": terminal_growth_rate,
    }


def estimate_net_debt(historical_df: pd.DataFrame) -> float:
    """Net Debt = Long-Term Debt - Cash and Equivalents (from latest historical period)."""
    periods = sorted([c for c in historical_df.columns if c != "line_item"])
    if not periods:
        return 0.0
    latest = periods[-1]

    def get_val(line_item):
        row = historical_df[historical_df["line_item"] == line_item]
        if row.empty or latest not in row.columns:
            return 0.0
        val = row[latest].iloc[0]
        return float(val) if pd.notna(val) else 0.0

    long_term_debt = get_val("long_term_debt")
    cash = get_val("cash_and_equivalents")
    return long_term_debt - cash


if __name__ == "__main__":
    import sys as _sys
    sys.path.append(str(Path(__file__).resolve().parent.parent / "forecasting"))
    from revenue_forecast import get_historical_data, derive_default_assumptions, project_income_statement, get_latest_period_value
    from balance_sheet import derive_working_capital_assumptions, project_working_capital, get_balancing_items
    from cash_flow import project_cash_flow

    if len(_sys.argv) < 2:
        print("Usage: python dcf.py <upload_id> [discount_rate] [terminal_growth_rate]")
    else:
        upload_id = _sys.argv[1]
        discount_rate = float(_sys.argv[2]) if len(_sys.argv) > 2 else 0.10
        terminal_growth_rate = float(_sys.argv[3]) if len(_sys.argv) > 3 else 0.025

        conn = duckdb.connect(str(DB_PATH), read_only=True)
        try:
            hist_df = get_historical_data(conn, upload_id)
            if hist_df.empty:
                print(f"No data found for upload_id={upload_id}")
            else:
                income_assumptions = derive_default_assumptions(hist_df)
                income_projection = project_income_statement(hist_df, income_assumptions, years_forward=5)

                wc_assumptions = derive_working_capital_assumptions(hist_df)
                starting_total_assets = get_latest_period_value(hist_df, "total_assets") or 0.0
                starting_current_assets = get_latest_period_value(hist_df, "total_current_assets") or 0.0
                starting_non_current_assets = starting_total_assets - starting_current_assets
                balancing_items = get_balancing_items(hist_df)

                working_capital = project_working_capital(
                    income_projection, hist_df, wc_assumptions,
                    starting_non_current_assets, balancing_items
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

                fcf_df = compute_free_cash_flow(cash_flow)
                print("--- Projected Free Cash Flow ---")
                print(fcf_df.to_string(index=False))

                net_debt = estimate_net_debt(hist_df)
                result = run_dcf(fcf_df, discount_rate, terminal_growth_rate, net_debt)

                print(f"\n--- DCF Valuation (discount rate={discount_rate:.1%}, terminal growth={terminal_growth_rate:.1%}) ---")
                print(result["detail"][["period", "free_cash_flow", "discounted_fcf"]].to_string(index=False))
                print(f"\nSum of Discounted FCFs:      ${result['sum_discounted_fcf']:,.2f}")
                print(f"Terminal Value:               ${result['terminal_value']:,.2f}")
                print(f"Discounted Terminal Value:    ${result['discounted_terminal_value']:,.2f}")
                print(f"Enterprise Value:              ${result['enterprise_value']:,.2f}")
                print(f"Net Debt:                      ${result['net_debt']:,.2f}")
                print(f"Implied Equity Value:          ${result['equity_value']:,.2f}")
        finally:
            conn.close()