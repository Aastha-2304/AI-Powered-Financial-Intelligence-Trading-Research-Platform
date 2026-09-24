"""
Common-Size and Horizontal Analysis for AI Financial Intelligence Platform.
Two classic statement-analysis views on top of the historical line-item
data already collected elsewhere in the app:

- Common-size: every line expressed as a % of a base line (revenue for
  income statement items, total assets for balance sheet items) --
  lets you compare companies of very different sizes on equal footing.
- Horizontal (indexed) analysis: every line indexed to the first
  available period = 100, so growth/decline patterns are immediately
  visible regardless of the underlying dollar scale.
"""
import pandas as pd

INCOME_STATEMENT_ITEMS = [
    "revenue", "cost_of_goods_sold", "gross_profit", "operating_expenses",
    "research_development", "operating_income", "interest_expense",
    "pretax_income", "tax_expense", "net_income",
]

BALANCE_SHEET_ITEMS = [
    "cash_and_equivalents", "accounts_receivable", "inventory",
    "total_current_assets", "total_assets", "accounts_payable",
    "total_current_liabilities", "long_term_debt", "total_liabilities",
    "total_equity", "retained_earnings",
]


def compute_common_size(hist_df: pd.DataFrame, statement: str = "income") -> pd.DataFrame:
    """statement: 'income' (base = revenue) or 'balance' (base = total_assets)."""
    items = INCOME_STATEMENT_ITEMS if statement == "income" else BALANCE_SHEET_ITEMS
    base_item = "revenue" if statement == "income" else "total_assets"

    periods = sorted([c for c in hist_df.columns if c != "line_item"])
    base_row = hist_df[hist_df["line_item"] == base_item]
    if base_row.empty:
        return pd.DataFrame()
    base_row = base_row.iloc[0]

    rows = []
    for item in items:
        row = hist_df[hist_df["line_item"] == item]
        if row.empty:
            continue
        row = row.iloc[0]
        record = {"line_item": item}
        for p in periods:
            base_val = base_row.get(p)
            val = row.get(p)
            record[p] = (val / base_val) if (base_val not in (None, 0) and val is not None) else None
        rows.append(record)

    return pd.DataFrame(rows)


def compute_horizontal(hist_df: pd.DataFrame, statement: str = "income") -> pd.DataFrame:
    """Every line indexed to its own first available period = 100."""
    items = INCOME_STATEMENT_ITEMS if statement == "income" else BALANCE_SHEET_ITEMS
    periods = sorted([c for c in hist_df.columns if c != "line_item"])

    rows = []
    for item in items:
        row = hist_df[hist_df["line_item"] == item]
        if row.empty:
            continue
        row = row.iloc[0]
        values = [row.get(p) for p in periods]
        base_val = next((v for v in values if v not in (None, 0)), None)
        if base_val is None:
            continue
        record = {"line_item": item}
        for p, v in zip(periods, values):
            record[p] = (v / base_val * 100) if v is not None else None
        rows.append(record)

    return pd.DataFrame(rows)