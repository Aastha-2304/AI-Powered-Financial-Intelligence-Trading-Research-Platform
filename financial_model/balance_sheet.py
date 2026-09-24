"""
Balance Sheet projection module for AI Financial Intelligence Platform
Projects working capital items and equity forward using historical
drivers (days sales outstanding, days inventory, days payable, etc.).
"""
import sys
from pathlib import Path
import duckdb
import pandas as pd
import numpy as np

sys.stdout.reconfigure(encoding="utf-8")

sys.path.append(str(Path(__file__).resolve().parent.parent))
from config import DB_PATH


def _get_row_values(df: pd.DataFrame, line_item: str, periods: list) -> list:
    row = df[df["line_item"] == line_item]
    if row.empty:
        return [None] * len(periods)
    return [row[p].iloc[0] if p in row.columns and pd.notna(row[p].iloc[0]) else None for p in periods]


def get_latest_value(df: pd.DataFrame, line_item: str) -> float:
    periods = sorted([c for c in df.columns if c != "line_item"])
    if not periods:
        return None
    return _get_row_values(df, line_item, periods)[-1]


def derive_working_capital_assumptions(df: pd.DataFrame) -> dict:
    """
    Derives balance-sheet drivers from history:
    - days_sales_outstanding (DSO): how many days of revenue sit in AR
    - days_inventory_outstanding (DIO): how many days of COGS sit in inventory
    - days_payable_outstanding (DPO): how many days of COGS sit in AP
    - non_current_asset_pct_revenue: kept for reference, not used in projection
    - other_current_liab_pct_cogs: current liabilities beyond AP, as % of COGS
    """
    periods = sorted([c for c in df.columns if c != "line_item"])

    revenue = _get_row_values(df, "revenue", periods)
    cogs = _get_row_values(df, "cost_of_goods_sold", periods)
    ar = _get_row_values(df, "accounts_receivable", periods)
    inventory = _get_row_values(df, "inventory", periods)
    ap = _get_row_values(df, "accounts_payable", periods)
    total_assets = _get_row_values(df, "total_assets", periods)
    total_current_assets = _get_row_values(df, "total_current_assets", periods)
    total_current_liabilities = _get_row_values(df, "total_current_liabilities", periods)

    dso_vals = [a / r * 365 for a, r in zip(ar, revenue) if a is not None and r not in (None, 0)]
    dio_vals = [i / c * 365 for i, c in zip(inventory, cogs) if i is not None and c not in (None, 0)]
    dpo_vals = [p / c * 365 for p, c in zip(ap, cogs) if p is not None and c not in (None, 0)]

    non_current_assets = [
        (ta - tca) if ta is not None and tca is not None else None
        for ta, tca in zip(total_assets, total_current_assets)
    ]
    nca_pct_vals = [nca / r for nca, r in zip(non_current_assets, revenue)
                     if nca is not None and r not in (None, 0)]

    other_curr_liab = [
        (tcl - p) if tcl is not None and p is not None else None
        for tcl, p in zip(total_current_liabilities, ap)
    ]
    other_liab_pct_vals = [ocl / c for ocl, c in zip(other_curr_liab, cogs)
                             if ocl is not None and c not in (None, 0)]

    return {
        "days_sales_outstanding": round(float(np.mean(dso_vals)), 1) if dso_vals else 45.0,
        "days_inventory_outstanding": round(float(np.mean(dio_vals)), 1) if dio_vals else 60.0,
        "days_payable_outstanding": round(float(np.mean(dpo_vals)), 1) if dpo_vals else 45.0,
        "non_current_asset_pct_revenue": round(float(np.mean(nca_pct_vals)), 4) if nca_pct_vals else 0.30,
        "other_current_liab_pct_cogs": round(float(np.mean(other_liab_pct_vals)), 4) if other_liab_pct_vals else 0.10,
    }


def get_balancing_items(historical_df: pd.DataFrame) -> dict:
    """
    Some historical balance sheets include line items beyond what our
    canonical fields capture (e.g. prepaid expenses, deferred tax
    liabilities). Rather than ignore them -- which would silently break
    the balance sheet identity -- we compute the residual once from the
    latest historical period and hold it flat across the projection.
    This mirrors standard modeling practice ("other assets / other
    liabilities" plug lines).
    """
    total_current_assets = get_latest_value(historical_df, "total_current_assets") or 0.0
    cash = get_latest_value(historical_df, "cash_and_equivalents") or 0.0
    ar = get_latest_value(historical_df, "accounts_receivable") or 0.0
    inventory = get_latest_value(historical_df, "inventory") or 0.0
    other_current_assets = total_current_assets - cash - ar - inventory

    total_liabilities = get_latest_value(historical_df, "total_liabilities") or 0.0
    total_current_liabilities = get_latest_value(historical_df, "total_current_liabilities") or 0.0
    long_term_debt = get_latest_value(historical_df, "long_term_debt") or 0.0
    other_noncurrent_liabilities = total_liabilities - total_current_liabilities - long_term_debt

    return {
        "other_current_assets": round(other_current_assets, 2),
        "other_noncurrent_liabilities": round(other_noncurrent_liabilities, 2),
    }


def project_working_capital(income_projection: pd.DataFrame, historical_df: pd.DataFrame,
                             wc_assumptions: dict, starting_non_current_assets: float,
                             balancing_items: dict) -> pd.DataFrame:
    """
    Projects AR, Inventory, AP, other current liabilities, non-current
    assets, and equity (rolled forward from net income) for each
    projected period. Non-current assets roll forward as prior balance
    + capex (depreciation not modeled -- a known simplification, since
    we don't have historical D&A to derive a rate from). Cash is added
    separately in finalize_balance_sheet() once cash_flow.py computes it.
    """
    long_term_debt = get_latest_value(historical_df, "long_term_debt") or 0.0
    prior_equity = get_latest_value(historical_df, "total_equity") or 0.0
    non_current_assets = starting_non_current_assets
    other_current_assets = balancing_items["other_current_assets"]
    other_noncurrent_liabilities = balancing_items["other_noncurrent_liabilities"]

    rows = []
    for _, row in income_projection.iterrows():
        revenue = row["revenue"]
        cogs = row["cost_of_goods_sold"]
        net_income = row["net_income"]
        capex = row["capital_expenditures"]

        ar = wc_assumptions["days_sales_outstanding"] / 365 * revenue
        inventory = wc_assumptions["days_inventory_outstanding"] / 365 * cogs
        ap = wc_assumptions["days_payable_outstanding"] / 365 * cogs
        other_current_liab = wc_assumptions["other_current_liab_pct_cogs"] * cogs

        # non-current assets roll forward: prior balance + this period's capex
        non_current_assets = non_current_assets + capex

        # equity rolls forward: prior equity + net income (assumes no dividends/buybacks)
        prior_equity = prior_equity + net_income

        rows.append({
            "period": row["period"],
            "accounts_receivable": round(ar, 2),
            "inventory": round(inventory, 2),
            "accounts_payable": round(ap, 2),
            "other_current_liabilities": round(other_current_liab, 2),
            "other_current_assets": other_current_assets,
            "non_current_assets": round(non_current_assets, 2),
            "long_term_debt": round(long_term_debt, 2),
            "other_noncurrent_liabilities": other_noncurrent_liabilities,
            "total_equity": round(prior_equity, 2),
        })

    return pd.DataFrame(rows)


def finalize_balance_sheet(working_capital: pd.DataFrame, cash_flow: pd.DataFrame) -> pd.DataFrame:
    """
    Combines the working-capital projection with the cash flow statement's
    ending cash to produce a complete projected balance sheet, and checks
    whether Assets = Liabilities + Equity (a genuine validation, not
    assumed by construction).
    """
    merged = working_capital.merge(cash_flow[["period", "ending_cash"]], on="period")
    merged = merged.rename(columns={"ending_cash": "cash_and_equivalents"})

    merged["total_current_assets"] = (
        merged["cash_and_equivalents"] + merged["accounts_receivable"]
        + merged["inventory"] + merged["other_current_assets"]
    )
    merged["total_assets"] = merged["total_current_assets"] + merged["non_current_assets"]

    merged["total_current_liabilities"] = merged["accounts_payable"] + merged["other_current_liabilities"]
    merged["total_liabilities"] = (
        merged["total_current_liabilities"] + merged["long_term_debt"]
        + merged["other_noncurrent_liabilities"]
    )

    merged["balance_check"] = merged["total_assets"] - (merged["total_liabilities"] + merged["total_equity"])
    merged["balances"] = merged["balance_check"].abs() < 1.0  # within $1 rounding tolerance

    return merged


if __name__ == "__main__":
    import sys as _sys
    sys.path.append(str(Path(__file__).resolve().parent.parent / "forecasting"))
    from revenue_forecast import get_historical_data, derive_default_assumptions, project_income_statement, get_latest_period_value

    if len(_sys.argv) < 2:
        print("Usage: python balance_sheet.py <upload_id>")
    else:
        upload_id = _sys.argv[1]
        conn = duckdb.connect(str(DB_PATH), read_only=True)
        try:
            hist_df = get_historical_data(conn, upload_id)
            if hist_df.empty:
                print(f"No data found for upload_id={upload_id}")
            else:
                income_assumptions = derive_default_assumptions(hist_df)
                income_projection = project_income_statement(hist_df, income_assumptions, years_forward=5)

                wc_assumptions = derive_working_capital_assumptions(hist_df)
                print("--- Derived Working Capital Assumptions ---")
                for k, v in wc_assumptions.items():
                    print(f"{k}: {v}")

                starting_total_assets = get_latest_period_value(hist_df, "total_assets") or 0.0
                starting_current_assets = get_latest_period_value(hist_df, "total_current_assets") or 0.0
                starting_non_current_assets = starting_total_assets - starting_current_assets

                balancing_items = get_balancing_items(hist_df)
                print("\n--- Balancing Items (held constant) ---")
                for k, v in balancing_items.items():
                    print(f"{k}: {v}")

                working_capital = project_working_capital(
                    income_projection, hist_df, wc_assumptions,
                    starting_non_current_assets, balancing_items
                )
                print("\n--- Working Capital Projection (pre-cash) ---")
                print(working_capital.to_string(index=False))
        finally:
            conn.close()