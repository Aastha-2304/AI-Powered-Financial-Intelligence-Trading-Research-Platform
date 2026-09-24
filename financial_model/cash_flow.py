"""
Cash Flow projection module for AI Financial Intelligence Platform
Builds a projected cash flow statement using the indirect method,
starting from projected net income and working-capital changes.
"""
import sys
from pathlib import Path
import duckdb
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

sys.path.append(str(Path(__file__).resolve().parent.parent))
from config import DB_PATH


def project_cash_flow(income_projection: pd.DataFrame, working_capital: pd.DataFrame,
                       starting_cash: float, starting_ar: float = 0.0,
                       starting_inventory: float = 0.0, starting_ap: float = 0.0,
                       starting_other_liab: float = 0.0) -> pd.DataFrame:
    """
    Indirect-method cash flow:
      Operating CF = Net Income + D&A (approximated via capex, simplified)
                      - increase in AR - increase in Inventory
                      + increase in AP + increase in other current liabilities
      Investing CF = -Capex
      Financing CF = 0 (no new debt/equity assumed in base case)
      Ending Cash = Starting Cash + Operating CF + Investing CF + Financing CF
    """
    merged = income_projection.merge(working_capital, on="period")

    rows = []
    prev_ar, prev_inventory = starting_ar, starting_inventory
    prev_ap, prev_other_liab = starting_ap, starting_other_liab
    cash = starting_cash

    for _, row in merged.iterrows():
        net_income = row["net_income"]
        capex = row["capital_expenditures"]

        delta_ar = row["accounts_receivable"] - prev_ar
        delta_inventory = row["inventory"] - prev_inventory
        delta_ap = row["accounts_payable"] - prev_ap
        delta_other_liab = row["other_current_liabilities"] - prev_other_liab

        operating_cf = net_income - delta_ar - delta_inventory + delta_ap + delta_other_liab
        investing_cf = -capex
        financing_cf = 0.0

        net_change_in_cash = operating_cf + investing_cf + financing_cf
        cash = cash + net_change_in_cash

        rows.append({
            "period": row["period"],
            "net_income": round(net_income, 2),
            "change_in_ar": round(-delta_ar, 2),
            "change_in_inventory": round(-delta_inventory, 2),
            "change_in_ap": round(delta_ap, 2),
            "change_in_other_liab": round(delta_other_liab, 2),
            "cash_from_operations": round(operating_cf, 2),
            "capital_expenditures": round(-capex, 2),
            "cash_from_investing": round(investing_cf, 2),
            "cash_from_financing": round(financing_cf, 2),
            "net_change_in_cash": round(net_change_in_cash, 2),
            "ending_cash": round(cash, 2),
        })

        prev_ar = row["accounts_receivable"]
        prev_inventory = row["inventory"]
        prev_ap = row["accounts_payable"]
        prev_other_liab = row["other_current_liabilities"]

    return pd.DataFrame(rows)


if __name__ == "__main__":
    import sys as _sys
    sys.path.append(str(Path(__file__).resolve().parent.parent / "forecasting"))
    from revenue_forecast import get_historical_data, derive_default_assumptions, project_income_statement, get_latest_period_value
    from balance_sheet import derive_working_capital_assumptions, project_working_capital, finalize_balance_sheet, get_balancing_items

    if len(_sys.argv) < 2:
        print("Usage: python cash_flow.py <upload_id>")
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

                starting_total_assets = get_latest_period_value(hist_df, "total_assets") or 0.0
                starting_current_assets = get_latest_period_value(hist_df, "total_current_assets") or 0.0
                starting_non_current_assets = starting_total_assets - starting_current_assets

                balancing_items = get_balancing_items(hist_df)
                print("--- Balancing Items (held constant) ---")
                for k, v in balancing_items.items():
                    print(f"{k}: {v}")

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

                print("\n--- Projected Cash Flow Statement ---")
                print(cash_flow.to_string(index=False))

                complete_balance_sheet = finalize_balance_sheet(working_capital, cash_flow)
                print("\n--- Complete Projected Balance Sheet ---")
                print(complete_balance_sheet.to_string(index=False))

                print("\n--- Balance Check ---")
                for _, row in complete_balance_sheet.iterrows():
                    status = "OK" if row["balances"] else "MISMATCH"
                    print(f"{row['period']}: Assets={row['total_assets']:,.0f}, "
                          f"Liab+Equity={row['total_liabilities']+row['total_equity']:,.0f}, "
                          f"diff={row['balance_check']:,.2f} [{status}]")
        finally:
            conn.close()