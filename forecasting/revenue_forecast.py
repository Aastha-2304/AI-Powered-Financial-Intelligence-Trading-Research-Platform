"""
Revenue Forecast module for AI Financial Intelligence Platform
Derives historical assumptions and projects the income statement forward.
"""
import sys
from pathlib import Path
import duckdb
import pandas as pd
import numpy as np

sys.stdout.reconfigure(encoding="utf-8")

sys.path.append(str(Path(__file__).resolve().parent.parent))
from config import DB_PATH


def get_historical_data(conn, upload_id: str) -> pd.DataFrame:
    """Pull wide-format historical financial data for one upload."""
    long_df = conn.execute("""
        SELECT line_item, period, value FROM financial_data WHERE upload_id = ?
    """, [upload_id]).fetchdf()
    if long_df.empty:
        return pd.DataFrame()
    wide_df = long_df.pivot(index="line_item", columns="period", values="value").reset_index()
    wide_df.columns.name = None
    return wide_df


def _get_row_values(df: pd.DataFrame, line_item: str, periods: list) -> list:
    row = df[df["line_item"] == line_item]
    if row.empty:
        return [None] * len(periods)
    return [row[p].iloc[0] if p in row.columns and pd.notna(row[p].iloc[0]) else None for p in periods]


def derive_default_assumptions(df: pd.DataFrame) -> dict:
    """
    Calculates sensible default assumptions from historical trend:
    - revenue_growth_rate: average year-over-year growth
    - cogs_pct_revenue: average COGS as % of revenue
    - opex_pct_revenue: average operating expenses as % of revenue
    - tax_rate: average effective tax rate
    - capex_pct_revenue: average capex as % of revenue (defaults to 5% if no capex data)
    """
    periods = sorted([c for c in df.columns if c != "line_item"])
    if len(periods) < 2:
        return {
            "revenue_growth_rate": 0.05,
            "cogs_pct_revenue": 0.55,
            "opex_pct_revenue": 0.15,
            "tax_rate": 0.21,
            "capex_pct_revenue": 0.05,
        }

    revenue = _get_row_values(df, "revenue", periods)
    cogs = _get_row_values(df, "cost_of_goods_sold", periods)
    opex = _get_row_values(df, "operating_expenses", periods)
    pretax = _get_row_values(df, "pretax_income", periods)
    tax = _get_row_values(df, "tax_expense", periods)
    capex = _get_row_values(df, "capital_expenditures", periods)

    growth_rates = []
    for i in range(1, len(revenue)):
        if revenue[i] is not None and revenue[i - 1] not in (None, 0):
            growth_rates.append((revenue[i] - revenue[i - 1]) / revenue[i - 1])
    revenue_growth_rate = float(np.mean(growth_rates)) if growth_rates else 0.05

    cogs_pcts = [c / r for c, r in zip(cogs, revenue) if c is not None and r not in (None, 0)]
    opex_pcts = [o / r for o, r in zip(opex, revenue) if o is not None and r not in (None, 0)]
    cogs_pct_revenue = float(np.mean(cogs_pcts)) if cogs_pcts else 0.55
    opex_pct_revenue = float(np.mean(opex_pcts)) if opex_pcts else 0.15

    tax_rates = [t / p for t, p in zip(tax, pretax) if t is not None and p not in (None, 0)]
    tax_rate = float(np.mean(tax_rates)) if tax_rates else 0.21

    capex_pcts = [abs(c) / r for c, r in zip(capex, revenue) if c is not None and r not in (None, 0)]
    capex_pct_revenue = float(np.mean(capex_pcts)) if capex_pcts else 0.05

    return {
        "revenue_growth_rate": round(revenue_growth_rate, 4),
        "cogs_pct_revenue": round(cogs_pct_revenue, 4),
        "opex_pct_revenue": round(opex_pct_revenue, 4),
        "tax_rate": round(min(max(tax_rate, 0), 0.5), 4),
        "capex_pct_revenue": round(capex_pct_revenue, 4),
    }


def get_latest_period_value(df: pd.DataFrame, line_item: str) -> float:
    periods = sorted([c for c in df.columns if c != "line_item"])
    if not periods:
        return None
    return _get_row_values(df, line_item, periods)[-1]


def project_income_statement(df: pd.DataFrame, assumptions: dict, years_forward: int = 5) -> pd.DataFrame:
    """
    Projects a simplified income statement forward using the given assumptions.
    Starts from the most recent historical revenue and compounds forward.
    """
    periods = sorted([c for c in df.columns if c != "line_item"])
    last_period = periods[-1] if periods else "0"
    base_revenue = get_latest_period_value(df, "revenue")

    if base_revenue is None:
        raise ValueError("No historical revenue found -- cannot project forward.")

    try:
        last_year = int(last_period)
    except ValueError:
        last_year = 0

    rows = []
    revenue = base_revenue
    for i in range(1, years_forward + 1):
        revenue = revenue * (1 + assumptions["revenue_growth_rate"])
        cogs = revenue * assumptions["cogs_pct_revenue"]
        gross_profit = revenue - cogs
        opex = revenue * assumptions["opex_pct_revenue"]
        operating_income = gross_profit - opex
        pretax_income = operating_income
        tax_expense = max(pretax_income, 0) * assumptions["tax_rate"]
        net_income = pretax_income - tax_expense
        capex = revenue * assumptions["capex_pct_revenue"]

        period_label = str(last_year + i) if last_year else f"Year {i}"
        rows.append({
            "period": period_label,
            "revenue": round(revenue, 2),
            "cost_of_goods_sold": round(cogs, 2),
            "gross_profit": round(gross_profit, 2),
            "operating_expenses": round(opex, 2),
            "operating_income": round(operating_income, 2),
            "pretax_income": round(pretax_income, 2),
            "tax_expense": round(tax_expense, 2),
            "net_income": round(net_income, 2),
            "capital_expenditures": round(capex, 2),
        })

    return pd.DataFrame(rows)


if __name__ == "__main__":
    import sys as _sys
    if len(_sys.argv) < 2:
        print("Usage: python revenue_forecast.py <upload_id>")
    else:
        upload_id = _sys.argv[1]
        conn = duckdb.connect(str(DB_PATH), read_only=True)
        try:
            df = get_historical_data(conn, upload_id)
            if df.empty:
                print(f"No data found for upload_id={upload_id}")
            else:
                assumptions = derive_default_assumptions(df)
                print("--- Derived Default Assumptions ---")
                for k, v in assumptions.items():
                    print(f"{k}: {v}")

                projection = project_income_statement(df, assumptions, years_forward=5)
                print("\n--- 5-Year Income Statement Projection ---")
                print(projection.to_string(index=False))
        finally:
            conn.close()