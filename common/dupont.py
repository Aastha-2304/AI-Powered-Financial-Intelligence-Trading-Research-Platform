"""
DuPont ROE Decomposition for AI Financial Intelligence Platform.
Breaks Return on Equity into its three classic drivers:
    ROE = Net Margin x Asset Turnover x Equity Multiplier
         (profitability)  (efficiency)    (leverage)
This shows WHY ROE moved -- did the company get more profitable, use its
assets better, or just take on more debt -- rather than just reporting
the single ROE number.
"""
import pandas as pd


def compute_dupont_series(hist_df: pd.DataFrame) -> pd.DataFrame:
    """hist_df is the wide-format historical data (line_item + one column
    per period) already used everywhere else in the app. Returns one row
    per period with each DuPont component plus the resulting ROE."""

    def get_row(line_item):
        row = hist_df[hist_df["line_item"] == line_item]
        return row.iloc[0] if not row.empty else None

    revenue_row = get_row("revenue")
    net_income_row = get_row("net_income")
    total_assets_row = get_row("total_assets")
    total_equity_row = get_row("total_equity")

    if any(r is None for r in (revenue_row, net_income_row, total_assets_row, total_equity_row)):
        return pd.DataFrame()

    periods = sorted([c for c in hist_df.columns if c != "line_item"])
    records = []
    for p in periods:
        revenue = revenue_row.get(p)
        net_income = net_income_row.get(p)
        total_assets = total_assets_row.get(p)
        total_equity = total_equity_row.get(p)

        if not all(v not in (None, 0) for v in (revenue, total_assets, total_equity)):
            continue

        net_margin = net_income / revenue
        asset_turnover = revenue / total_assets
        equity_multiplier = total_assets / total_equity
        roe = net_margin * asset_turnover * equity_multiplier

        records.append({
            "period": p,
            "net_margin": net_margin,
            "asset_turnover": asset_turnover,
            "equity_multiplier": equity_multiplier,
            "roe": roe,
        })

    return pd.DataFrame(records)


def interpret_dupont_trend(dupont_df: pd.DataFrame) -> str:
    """One-line plain-English read on what drove the change in ROE
    between the first and last period, for a quick headline takeaway."""
    if len(dupont_df) < 2:
        return "Not enough periods to identify a trend."

    first, last = dupont_df.iloc[0], dupont_df.iloc[-1]
    margin_delta = last["net_margin"] - first["net_margin"]
    turnover_delta = last["asset_turnover"] - first["asset_turnover"]
    leverage_delta = last["equity_multiplier"] - first["equity_multiplier"]

    drivers = {
        "profitability (net margin)": margin_delta,
        "efficiency (asset turnover)": turnover_delta,
        "leverage (equity multiplier)": leverage_delta,
    }
    biggest_driver = max(drivers, key=lambda k: abs(drivers[k]))
    direction = "improved" if drivers[biggest_driver] > 0 else "declined"

    roe_change = (last["roe"] - first["roe"]) * 100
    return (
        f"ROE moved from {first['roe']:.1%} to {last['roe']:.1%} "
        f"({roe_change:+.1f} pts), driven mainly by {direction} {biggest_driver}."
    )