"""
DCF Sensitivity Analysis for AI Financial Intelligence Platform.
Runs the existing DCF engine across a grid of discount rate x terminal
growth combinations, so the valuation is shown as a range driven by
assumption uncertainty rather than a single brittle point estimate --
the standard artifact expected in any real DCF writeup.
"""
import pandas as pd


def compute_dcf_sensitivity_grid(fcf_df, net_debt: float, run_dcf_fn,
                                   discount_rates=None, terminal_growths=None,
                                   value_key: str = "enterprise_value") -> pd.DataFrame:
    """Returns a DataFrame with discount rates as the index and terminal
    growth rates as columns, containing the requested DCF output value
    (enterprise_value or equity_value) for every combination.

    run_dcf_fn: pass the run_dcf function directly (dcf.run_dcf) so this
    module has no import dependency on the forecasting package -- keeps
    it reusable from any page without path-juggling.
    """
    if discount_rates is None:
        discount_rates = [0.06, 0.08, 0.10, 0.12, 0.14, 0.16]
    if terminal_growths is None:
        terminal_growths = [0.00, 0.015, 0.025, 0.035, 0.05]

    rows = {}
    for dr in discount_rates:
        row = {}
        for tg in terminal_growths:
            if tg >= dr:
                row[tg] = None  # terminal growth must be below discount rate, or the model breaks
                continue
            try:
                result = run_dcf_fn(fcf_df, dr, tg, net_debt)
                row[tg] = result.get(value_key)
            except (ValueError, ZeroDivisionError):
                row[tg] = None
        rows[dr] = row

    grid = pd.DataFrame(rows).T  # discount rates as rows after transpose
    grid.index.name = "discount_rate"
    grid.columns.name = "terminal_growth"
    return grid