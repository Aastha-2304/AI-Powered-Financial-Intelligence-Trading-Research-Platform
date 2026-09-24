"""
Ratios module for AI Financial Intelligence Platform
Computes profitability, liquidity, leverage, and efficiency ratios
from canonically-mapped financial data.
"""
import sys
from pathlib import Path
import duckdb
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

sys.path.append(str(Path(__file__).resolve().parent.parent))
from config import DB_PATH


def load_wide_from_db(conn, upload_id: str) -> pd.DataFrame:
    """
    Pulls one upload's financial_data (long format: line_item, period, value)
    and pivots it back to wide format (line_item, period1, period2, ...) --
    the same shape used throughout the ETL pipeline.
    """
    long_df = conn.execute("""
        SELECT line_item, period, value FROM financial_data
        WHERE upload_id = ?
    """, [upload_id]).fetchdf()

    if long_df.empty:
        return pd.DataFrame(columns=["line_item"])

    wide_df = long_df.pivot(index="line_item", columns="period", values="value").reset_index()
    wide_df.columns.name = None
    return wide_df


def _get_value(df: pd.DataFrame, line_item: str, period: str):
    row = df[df["line_item"] == line_item]
    if row.empty or period not in row.columns:
        return None
    val = row[period].iloc[0]
    return None if pd.isna(val) else float(val)


def _safe_div(numerator, denominator):
    """Division that returns None instead of crashing on missing/zero values."""
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


# ---------------------------------------------------------------------
# Ratio calculations -- each returns a list of {ratio_name, period, value}
# ---------------------------------------------------------------------

def compute_profitability_ratios(df: pd.DataFrame, periods: list) -> list:
    results = []
    for period in periods:
        revenue = _get_value(df, "revenue", period)
        gross_profit = _get_value(df, "gross_profit", period)
        operating_income = _get_value(df, "operating_income", period)
        net_income = _get_value(df, "net_income", period)
        total_assets = _get_value(df, "total_assets", period)
        total_equity = _get_value(df, "total_equity", period)

        ratios = {
            "gross_margin_pct": _safe_div(gross_profit, revenue),
            "operating_margin_pct": _safe_div(operating_income, revenue),
            "net_margin_pct": _safe_div(net_income, revenue),
            "return_on_assets_pct": _safe_div(net_income, total_assets),
            "return_on_equity_pct": _safe_div(net_income, total_equity),
        }
        for name, value in ratios.items():
            results.append({
                "category": "profitability", "ratio_name": name, "period": period,
                "value": round(value * 100, 2) if value is not None else None,
            })
    return results


def compute_liquidity_ratios(df: pd.DataFrame, periods: list) -> list:
    results = []
    for period in periods:
        current_assets = _get_value(df, "total_current_assets", period)
        current_liabilities = _get_value(df, "total_current_liabilities", period)
        inventory = _get_value(df, "inventory", period)
        cash = _get_value(df, "cash_and_equivalents", period)

        quick_assets = None
        if current_assets is not None and inventory is not None:
            quick_assets = current_assets - inventory

        ratios = {
            "current_ratio": _safe_div(current_assets, current_liabilities),
            "quick_ratio": _safe_div(quick_assets, current_liabilities),
            "cash_ratio": _safe_div(cash, current_liabilities),
        }
        for name, value in ratios.items():
            results.append({
                "category": "liquidity", "ratio_name": name, "period": period,
                "value": round(value, 2) if value is not None else None,
            })
    return results


def compute_leverage_ratios(df: pd.DataFrame, periods: list) -> list:
    results = []
    for period in periods:
        total_liabilities = _get_value(df, "total_liabilities", period)
        total_equity = _get_value(df, "total_equity", period)
        total_assets = _get_value(df, "total_assets", period)
        operating_income = _get_value(df, "operating_income", period)
        interest_expense = _get_value(df, "interest_expense", period)

        ratios = {
            "debt_to_equity": _safe_div(total_liabilities, total_equity),
            "debt_to_assets": _safe_div(total_liabilities, total_assets),
            "interest_coverage": _safe_div(operating_income, interest_expense),
        }
        for name, value in ratios.items():
            results.append({
                "category": "leverage", "ratio_name": name, "period": period,
                "value": round(value, 2) if value is not None else None,
            })
    return results


def compute_efficiency_ratios(df: pd.DataFrame, periods: list) -> list:
    results = []
    for period in periods:
        revenue = _get_value(df, "revenue", period)
        total_assets = _get_value(df, "total_assets", period)
        accounts_receivable = _get_value(df, "accounts_receivable", period)
        cogs = _get_value(df, "cost_of_goods_sold", period)
        inventory = _get_value(df, "inventory", period)

        ratios = {
            "asset_turnover": _safe_div(revenue, total_assets),
            "receivables_turnover": _safe_div(revenue, accounts_receivable),
            "inventory_turnover": _safe_div(cogs, inventory),
        }
        for name, value in ratios.items():
            results.append({
                "category": "efficiency", "ratio_name": name, "period": period,
                "value": round(value, 2) if value is not None else None,
            })
    return results


def compute_all_ratios(df: pd.DataFrame) -> pd.DataFrame:
    periods = [c for c in df.columns if c != "line_item"]
    all_results = (
        compute_profitability_ratios(df, periods)
        + compute_liquidity_ratios(df, periods)
        + compute_leverage_ratios(df, periods)
        + compute_efficiency_ratios(df, periods)
    )
    return pd.DataFrame(all_results)


def store_ratios(conn, upload_id: str, company_name: str, ratios_df: pd.DataFrame):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS financial_ratios (
            upload_id VARCHAR,
            company_name VARCHAR,
            category VARCHAR,
            ratio_name VARCHAR,
            period VARCHAR,
            value DOUBLE
        )
    """)
    # clear any previous ratios for this upload (idempotent re-run)
    conn.execute("DELETE FROM financial_ratios WHERE upload_id = ?", [upload_id])

    out = ratios_df.copy()
    out.insert(0, "upload_id", upload_id)
    out.insert(1, "company_name", company_name)
    conn.register("temp_ratios", out)
    conn.execute("INSERT INTO financial_ratios SELECT * FROM temp_ratios")
    conn.unregister("temp_ratios")
    print(f"Stored {len(out)} ratio values for upload {upload_id}")


if __name__ == "__main__":
    import sys as _sys

    if len(_sys.argv) < 2:
        print("Usage: python ratios.py <upload_id>")
        print("\nTip: run this to see available upload_ids:")
        print("  python -c \"import duckdb; print(duckdb.connect('database/financial_warehouse.duckdb', read_only=True).execute('SELECT upload_id, company_name FROM uploads').fetchdf())\"")
    else:
        upload_id = _sys.argv[1]
        conn = duckdb.connect(str(DB_PATH))
        try:
            wide_df = load_wide_from_db(conn, upload_id)
            if wide_df.empty:
                print(f"No data found for upload_id={upload_id}")
            else:
                company_row = conn.execute(
                    "SELECT company_name FROM uploads WHERE upload_id = ?", [upload_id]
                ).fetchone()
                company_name = company_row[0] if company_row else "Unknown"

                ratios_df = compute_all_ratios(wide_df)
                print(f"\n--- Financial Ratios for {company_name} ---")
                print(ratios_df.to_string(index=False))

                store_ratios(conn, upload_id, company_name, ratios_df)
        finally:
            conn.close()