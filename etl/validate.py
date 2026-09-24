"""
Validate module for AI Financial Intelligence Platform
Runs accounting-identity checks, completeness checks, and anomaly
detection on canonically-mapped financial data.
"""
import sys
from pathlib import Path
import pandas as pd
import numpy as np

sys.stdout.reconfigure(encoding="utf-8")

sys.path.append(str(Path(__file__).resolve().parent.parent))
from config import REQUIRED_FIELDS


def _get_value(df: pd.DataFrame, line_item: str, period: str):
    """Look up a single value for a line_item + period, or None if missing."""
    row = df[df["line_item"] == line_item]
    if row.empty or period not in row.columns:
        return None
    val = row[period].iloc[0]
    return None if pd.isna(val) else float(val)


def check_completeness(df: pd.DataFrame) -> pd.DataFrame:
    """Flag any required field missing entirely from the uploaded data."""
    present_fields = set(df["line_item"].unique())
    issues = []
    for field in REQUIRED_FIELDS:
        if field not in present_fields:
            issues.append({
                "check": "completeness",
                "line_item": field,
                "period": None,
                "severity": "HIGH",
                "message": f"Required field '{field}' is missing from the uploaded data.",
            })
    return pd.DataFrame(issues)


def check_accounting_identity(df: pd.DataFrame, periods: list) -> pd.DataFrame:
    """
    Core check: Total Assets = Total Liabilities + Total Equity.
    A mismatch here usually means a data entry error or a genuinely
    unbalanced statement -- the single most important validation check.
    """
    issues = []
    for period in periods:
        assets = _get_value(df, "total_assets", period)
        liabilities = _get_value(df, "total_liabilities", period)
        equity = _get_value(df, "total_equity", period)

        if assets is None or liabilities is None or equity is None:
            continue  # completeness check already flags missing fields

        diff = assets - (liabilities + equity)
        # allow small rounding tolerance (0.5% of total assets)
        tolerance = abs(assets) * 0.005
        if abs(diff) > tolerance:
            issues.append({
                "check": "accounting_identity",
                "line_item": "total_assets vs total_liabilities+total_equity",
                "period": period,
                "severity": "HIGH",
                "message": (f"Balance sheet does not balance in {period}: "
                            f"Assets={assets:,.0f}, Liabilities+Equity={liabilities + equity:,.0f}, "
                            f"difference={diff:,.0f}"),
            })
    return pd.DataFrame(issues)


def check_income_statement_flow(df: pd.DataFrame, periods: list) -> pd.DataFrame:
    """
    Checks that income statement line items flow logically:
    Gross Profit ~= Revenue - COGS, Net Income should be less than Pretax Income
    (since tax is subtracted), Operating Income should be positive if company
    reports one at all in a healthy range, etc.
    """
    issues = []
    for period in periods:
        revenue = _get_value(df, "revenue", period)
        cogs = _get_value(df, "cost_of_goods_sold", period)
        gross_profit = _get_value(df, "gross_profit", period)

        if revenue is not None and cogs is not None and gross_profit is not None:
            expected_gp = revenue - cogs
            diff = abs(gross_profit - expected_gp)
            tolerance = abs(revenue) * 0.01
            if diff > tolerance:
                issues.append({
                    "check": "income_statement_flow",
                    "line_item": "gross_profit",
                    "period": period,
                    "severity": "MEDIUM",
                    "message": (f"Gross Profit in {period} ({gross_profit:,.0f}) doesn't match "
                                f"Revenue - COGS ({expected_gp:,.0f})."),
                })

        pretax = _get_value(df, "pretax_income", period)
        net_income = _get_value(df, "net_income", period)
        if pretax is not None and net_income is not None and net_income > pretax:
            issues.append({
                "check": "income_statement_flow",
                "line_item": "net_income",
                "period": period,
                "severity": "MEDIUM",
                "message": (f"Net Income in {period} ({net_income:,.0f}) is greater than "
                            f"Pretax Income ({pretax:,.0f}) -- taxes should reduce income, not increase it."),
            })

    return pd.DataFrame(issues)


def check_negative_values(df: pd.DataFrame, periods: list) -> pd.DataFrame:
    """Flag line items that should never realistically be negative."""
    should_be_nonnegative = [
        "revenue", "total_assets", "total_current_assets", "cash_and_equivalents",
        "inventory", "accounts_receivable", "total_liabilities", "total_equity",
    ]
    issues = []
    for period in periods:
        for field in should_be_nonnegative:
            val = _get_value(df, field, period)
            if val is not None and val < 0:
                issues.append({
                    "check": "negative_value",
                    "line_item": field,
                    "period": period,
                    "severity": "MEDIUM",
                    "message": f"'{field}' is negative in {period} ({val:,.0f}), which is unusual.",
                })
    return pd.DataFrame(issues)


def check_period_over_period_anomalies(df: pd.DataFrame, periods: list) -> pd.DataFrame:
    """
    Flag any line item that changes more than 75% from one period to the
    next -- could be a real event, or could be a data entry error worth
    a second look.
    """
    issues = []
    sorted_periods = sorted(periods)
    for i in range(1, len(sorted_periods)):
        prev_period, curr_period = sorted_periods[i - 1], sorted_periods[i]
        for line_item in df["line_item"].unique():
            prev_val = _get_value(df, line_item, prev_period)
            curr_val = _get_value(df, line_item, curr_period)
            if prev_val is None or curr_val is None or prev_val == 0:
                continue
            pct_change = (curr_val - prev_val) / abs(prev_val)
            if abs(pct_change) > 0.75:
                issues.append({
                    "check": "period_over_period_anomaly",
                    "line_item": line_item,
                    "period": curr_period,
                    "severity": "LOW",
                    "message": (f"'{line_item}' changed {pct_change*100:+.1f}% from {prev_period} "
                                f"({prev_val:,.0f}) to {curr_period} ({curr_val:,.0f})."),
                })
    return pd.DataFrame(issues)


def run_all_validations(df: pd.DataFrame) -> pd.DataFrame:
    """
    df is expected to already be canonically mapped (line_item column
    with canonical field names, plus one column per period).
    """
    periods = [c for c in df.columns if c != "line_item"]

    all_issues = pd.concat([
        check_completeness(df),
        check_accounting_identity(df, periods),
        check_income_statement_flow(df, periods),
        check_negative_values(df, periods),
        check_period_over_period_anomalies(df, periods),
    ], ignore_index=True)

    return all_issues


def data_quality_score(df: pd.DataFrame, issues: pd.DataFrame) -> dict:
    """A simple 0-100 score: starts at 100, deducted per issue by severity."""
    deductions = {"HIGH": 15, "MEDIUM": 7, "LOW": 2}
    score = 100
    for _, row in issues.iterrows():
        score -= deductions.get(row["severity"], 0)
    score = max(0, score)

    return {
        "score": score,
        "total_issues": len(issues),
        "high_severity": (issues["severity"] == "HIGH").sum() if not issues.empty else 0,
        "medium_severity": (issues["severity"] == "MEDIUM").sum() if not issues.empty else 0,
        "low_severity": (issues["severity"] == "LOW").sum() if not issues.empty else 0,
    }


if __name__ == "__main__":
    import sys as _sys
    from extract import extract_file
    from transform import map_raw_dataframe, apply_mapping

    if len(_sys.argv) < 2:
        print("Usage: python validate.py <path_to_file>")
    else:
        raw_df = extract_file(_sys.argv[1])
        mapping = map_raw_dataframe(raw_df)
        clean_df = apply_mapping(raw_df, mapping)

        print("\n--- Canonically Mapped Data ---")
        print(clean_df.to_string(index=False))

        issues = run_all_validations(clean_df)

        print("\n--- Validation Issues ---")
        if issues.empty:
            print("No issues found.")
        else:
            print(issues.to_string(index=False))

        score = data_quality_score(clean_df, issues)
        print("\n--- Data Quality Score ---")
        for k, v in score.items():
            print(f"{k}: {v}")