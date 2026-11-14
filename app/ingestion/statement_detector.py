"""
Statement and period detection engine.
Detects whether tabular data represents an Income Statement, Balance Sheet, or Cash Flow,
and detects whether columns/rows represent reporting periods (e.g., 2021, 2022, 2023, 2023-Q1).
"""
import re
from typing import Tuple, List, Dict, Optional, Set
import pandas as pd

from app.core.constants import STATEMENT_INCOME, STATEMENT_BALANCE_SHEET, STATEMENT_CASH_FLOW

# Signature keywords characteristic of each statement
INCOME_SIGNATURES = {
    "revenue", "sales", "cogs", "cost of goods", "cost of revenue", "gross profit",
    "operating expenses", "operating income", "ebit", "net income", "earnings per share",
    "eps", "interest expense", "tax expense", "pretax income"
}

BALANCE_SHEET_SIGNATURES = {
    "assets", "cash and cash equivalents", "accounts receivable", "inventory",
    "current assets", "total assets", "accounts payable", "current liabilities",
    "long-term debt", "retained earnings", "stockholders' equity", "shareholders' equity",
    "liabilities", "total liabilities"
}

CASH_FLOW_SIGNATURES = {
    "cash flow", "operating activities", "investing activities", "financing activities",
    "depreciation", "capital expenditures", "capex", "dividends paid", "free cash flow",
    "net change in cash"
}

PERIOD_YEAR_REGEX = re.compile(r"^(?:FY|CY)?\s*(19\d\d|20\d\d)\b", re.IGNORECASE)
PERIOD_QUARTER_REGEX = re.compile(r"^(?:FY|CY)?\s*(19\d\d|20\d\d)\s*[-/_\s]?\s*Q([1-4])\b|^(?:Q([1-4]))\s*[-/_\s]?\s*(19\d\d|20\d\d)\b", re.IGNORECASE)


class StatementDetector:
    """Classifies financial statement type and identifies period columns."""

    @classmethod
    def normalize_period_header(cls, header: str) -> Optional[Tuple[str, str]]:
        """
        Extracts canonical period format from a column header string or integer.
        Returns (canonical_period, period_type) e.g. ('2023', 'annual') or ('2023-Q1', 'quarterly').
        """
        raw = str(header).strip()

        # Check quarterly
        q_match = PERIOD_QUARTER_REGEX.search(raw)
        if q_match:
            groups = q_match.groups()
            if groups[0] and groups[1]:
                year, qtr = groups[0], groups[1]
            else:
                year, qtr = groups[3], groups[2]
            return f"{year}-Q{qtr}", "quarterly"

        # Check annual
        y_match = PERIOD_YEAR_REGEX.search(raw)
        if y_match:
            year = y_match.group(1)
            return year, "annual"

        return None

    @classmethod
    def detect_statement_type(cls, df: pd.DataFrame, sheet_name: str = "") -> str:
        """
        Detects statement type using combined sheet name context and row label frequency.
        """
        name_lower = str(sheet_name).lower()
        if "income" in name_lower or "p&l" in name_lower or "operations" in name_lower:
            return STATEMENT_INCOME
        if "balance" in name_lower or "position" in name_lower:
            return STATEMENT_BALANCE_SHEET
        if "cash" in name_lower or "flow" in name_lower:
            return STATEMENT_CASH_FLOW

        # Scan text entries in the dataframe (typically first 1-2 columns)
        all_text = " ".join(
            df.iloc[:, 0].dropna().astype(str).tolist() +
            (df.iloc[:, 1].dropna().astype(str).tolist() if df.shape[1] > 1 else [])
        ).lower()

        inc_count = sum(1 for kw in INCOME_SIGNATURES if kw in all_text)
        bs_count = sum(1 for kw in BALANCE_SHEET_SIGNATURES if kw in all_text)
        cf_count = sum(1 for kw in CASH_FLOW_SIGNATURES if kw in all_text)

        if bs_count > inc_count and bs_count > cf_count:
            return STATEMENT_BALANCE_SHEET
        if cf_count > inc_count and cf_count > bs_count:
            return STATEMENT_CASH_FLOW
        return STATEMENT_INCOME

    @classmethod
    def identify_layout(cls, df: pd.DataFrame) -> Tuple[int, List[Tuple[int, str, str]]]:
        """
        Identifies the header label column index and the period columns.
        Returns:
            label_col_idx: column containing financial line item text labels.
            period_cols: list of (col_idx, canonical_period, period_type).
        """
        period_cols: List[Tuple[int, str, str]] = []

        # Find columns whose names match dates/years
        for idx, col in enumerate(df.columns):
            norm = cls.normalize_period_header(col)
            if norm:
                period_cols.append((idx, norm[0], norm[1]))

        # The label column is typically the first non-period column
        period_col_indices = {p[0] for p in period_cols}
        label_col_idx = 0
        for idx in range(df.shape[1]):
            if idx not in period_col_indices:
                label_col_idx = idx
                break

        return label_col_idx, period_cols
