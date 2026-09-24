"""
Altman Z'-Score for AI Financial Intelligence Platform.
Uses Altman's private-firm model (Z-prime), which substitutes book value
of equity for market value of equity -- appropriate here since uploaded
financials have no market cap. Formula and risk bands are the standard,
widely-taught version (Altman, 1983):

    Z' = 0.717*A + 0.847*B + 3.107*C + 0.420*D + 0.998*E

    A = Working Capital / Total Assets
    B = Retained Earnings / Total Assets
    C = EBIT / Total Assets
    D = Book Value of Equity / Total Liabilities
    E = Revenue / Total Assets

Zones:
    Z' > 2.90        -> Safe Zone
    1.23 <= Z' <= 2.90 -> Grey Zone
    Z' < 1.23        -> Distress Zone
"""
import pandas as pd


def _get_value(hist_df, line_item, period):
    row = hist_df[hist_df["line_item"] == line_item]
    if row.empty:
        return None
    return row.iloc[0].get(period)


def compute_zscore_series(hist_df: pd.DataFrame) -> pd.DataFrame:
    periods = sorted([c for c in hist_df.columns if c != "line_item"])
    records = []

    for p in periods:
        total_assets = _get_value(hist_df, "total_assets", p)
        total_liabilities = _get_value(hist_df, "total_liabilities", p)
        total_current_assets = _get_value(hist_df, "total_current_assets", p)
        total_current_liabilities = _get_value(hist_df, "total_current_liabilities", p)
        retained_earnings = _get_value(hist_df, "retained_earnings", p)
        revenue = _get_value(hist_df, "revenue", p)
        total_equity = _get_value(hist_df, "total_equity", p)

        # EBIT: prefer the direct line item, fall back to reconstructing it
        ebit = _get_value(hist_df, "operating_income", p)
        if ebit is None:
            net_income = _get_value(hist_df, "net_income", p)
            tax_expense = _get_value(hist_df, "tax_expense", p) or 0
            interest_expense = _get_value(hist_df, "interest_expense", p) or 0
            ebit = (net_income or 0) + tax_expense + interest_expense

        required = [total_assets, total_liabilities, total_current_assets,
                    total_current_liabilities, retained_earnings, revenue, total_equity]
        if any(v in (None, 0) for v in required) or total_assets == 0:
            continue

        working_capital = total_current_assets - total_current_liabilities

        A = working_capital / total_assets
        B = retained_earnings / total_assets
        C = ebit / total_assets
        D = total_equity / total_liabilities if total_liabilities else 0
        E = revenue / total_assets

        z = 0.717 * A + 0.847 * B + 3.107 * C + 0.420 * D + 0.998 * E

        if z > 2.90:
            zone = "Safe"
        elif z >= 1.23:
            zone = "Grey"
        else:
            zone = "Distress"

        records.append({
            "period": p, "working_capital_pct_assets": A, "retained_earnings_pct_assets": B,
            "ebit_pct_assets": C, "equity_to_liabilities": D, "asset_turnover": E,
            "zscore": z, "zone": zone,
        })

    return pd.DataFrame(records)


def zone_status(zone: str) -> str:
    """Maps a Z-Score zone to a status_badge status string."""
    return {"Safe": "success", "Grey": "warning", "Distress": "error"}.get(zone, "warning")