"""
Earnings Quality Red-Flags for AI Financial Intelligence Platform.
A short checklist of classic signals analysts use to spot aggressive or
low-quality earnings. These are heuristics, not proof of wrongdoing --
they flag "worth investigating further," which is exactly how a real
analyst would use them.
"""
import pandas as pd


def _get_value(hist_df, line_item, period):
    row = hist_df[hist_df["line_item"] == line_item]
    if row.empty:
        return None
    return row.iloc[0].get(period)


def compute_accruals_ratio(hist_df: pd.DataFrame) -> pd.DataFrame:
    """Accruals Ratio = (Net Income - Operating Cash Flow) / Total Assets.
    A persistently large positive value means reported profit is running
    well ahead of actual cash generation -- a classic earnings-quality
    warning sign. Requires cash_from_operations, which may not always be
    present depending on what was uploaded."""
    periods = sorted([c for c in hist_df.columns if c != "line_item"])
    records = []
    for p in periods:
        net_income = _get_value(hist_df, "net_income", p)
        cfo = _get_value(hist_df, "cash_from_operations", p)
        total_assets = _get_value(hist_df, "total_assets", p)
        if net_income is None or cfo is None or not total_assets:
            continue
        accruals_ratio = (net_income - cfo) / total_assets
        records.append({
            "period": p, "net_income": net_income, "operating_cash_flow": cfo,
            "accruals_ratio": accruals_ratio,
            "flag": accruals_ratio > 0.10,  # >10% of assets is a commonly-used rule-of-thumb threshold
        })
    return pd.DataFrame(records)


def compute_revenue_receivables_divergence(hist_df: pd.DataFrame) -> pd.DataFrame:
    """Flags periods where accounts receivable grew meaningfully faster
    than revenue -- can indicate loose revenue recognition, channel
    stuffing, or customers struggling to pay."""
    periods = sorted([c for c in hist_df.columns if c != "line_item"])
    records = []
    prev_revenue, prev_ar = None, None
    for p in periods:
        revenue = _get_value(hist_df, "revenue", p)
        ar = _get_value(hist_df, "accounts_receivable", p)
        if revenue is None or ar is None:
            prev_revenue, prev_ar = revenue, ar
            continue
        if prev_revenue and prev_ar and prev_revenue != 0 and prev_ar != 0:
            revenue_growth = (revenue - prev_revenue) / prev_revenue
            ar_growth = (ar - prev_ar) / prev_ar
            divergence = ar_growth - revenue_growth
            records.append({
                "period": p, "revenue_growth": revenue_growth, "ar_growth": ar_growth,
                "divergence": divergence,
                "flag": divergence > 0.15,  # AR growing >15pts faster than revenue
            })
        prev_revenue, prev_ar = revenue, ar
    return pd.DataFrame(records)


def get_red_flag_summary(hist_df: pd.DataFrame) -> list:
    """Returns a list of plain-English warning strings for any flagged
    period across all checks -- meant to render directly as a checklist."""
    warnings = []

    accruals_df = compute_accruals_ratio(hist_df)
    if not accruals_df.empty and "flag" in accruals_df.columns:
        for _, row in accruals_df[accruals_df["flag"]].iterrows():
            warnings.append(
                f"{row['period']}: Accruals ratio of {row['accruals_ratio']:.1%} -- "
                f"net income is running well ahead of operating cash flow."
            )

    divergence_df = compute_revenue_receivables_divergence(hist_df)
    if not divergence_df.empty and "flag" in divergence_df.columns:
        for _, row in divergence_df[divergence_df["flag"]].iterrows():
            warnings.append(
                f"{row['period']}: Receivables grew {row['ar_growth']:.1%} vs revenue growth of "
                f"{row['revenue_growth']:.1%} -- a {row['divergence']:.1%} divergence worth investigating."
            )

    return warnings