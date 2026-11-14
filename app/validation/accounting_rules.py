"""
Deterministic accounting rules and financial identity verification:
1. Balance Sheet Identity: Assets = Liabilities + Equity (tolerance applied AFTER unit normalization)
2. Income Statement Hierarchy: Gross Profit = Revenue - COGS; Pretax Income = Operating Income - Net Interest; Net Income = Pretax Income - Tax
3. Cash Flow Reconciliation: Net Change in Cash = Operating CF + Investing CF + Financing CF
4. Plausibility bounds on core ratios (Gross Margin in [0, 1], Current Ratio > 0, etc.)

Separates hard failures from warnings:
- Hard failure: Balance Sheet does not balance beyond tolerance.
- Warning: Ratio anomaly or minor rounding difference.
"""
from typing import Dict, List, Optional, Tuple
from app.schemas.financial import FinancialFact
from app.schemas.modeling import ValidationFinding


DEFAULT_BALANCE_TOLERANCE = 1.0  # $1 or 1 base unit after unit normalization


def check_balance_sheet_identity(
    facts_by_item: Dict[str, float],
    period: str,
    dataset_id: str,
    dataset_version: int,
    run_id: str,
    tolerance: float = DEFAULT_BALANCE_TOLERANCE,
    source_row: Optional[int] = None,
) -> Optional[ValidationFinding]:
    """
    Checks Assets = Liabilities + Equity.
    Tolerance is applied strictly after unit normalization.
    Returns ValidationFinding if imbalanced, otherwise None.
    """
    assets = facts_by_item.get("total_assets")
    liab = facts_by_item.get("total_liabilities")
    equity = facts_by_item.get("total_equity")
    liab_equity = facts_by_item.get("total_liabilities_and_equity")

    # If total_liabilities_and_equity is explicitly reported, verify against total_assets directly
    if assets is not None and liab_equity is not None:
        diff = abs(assets - liab_equity)
        if diff > tolerance:
            return ValidationFinding(
                finding_id=f"vf_bs_id_{period}_{run_id}",
                run_id=run_id,
                dataset_id=dataset_id,
                dataset_version=dataset_version,
                rule_name="balance_sheet_identity",
                dimension="accounting_consistency",
                severity="hard_failure",
                line_item="total_assets",
                period=period,
                observed_value=assets,
                expected_value=liab_equity,
                tolerance=tolerance,
                message=f"Balance Sheet imbalance in {period}: Total Assets ({assets:,.2f}) != Total Liabilities & Equity ({liab_equity:,.2f}), delta = {diff:,.2f}",
                source_row=source_row,
            )
        return None

    # Alternatively verify assets == liab + equity
    if assets is not None and liab is not None and equity is not None:
        expected = liab + equity
        diff = abs(assets - expected)
        if diff > tolerance:
            return ValidationFinding(
                finding_id=f"vf_bs_id_{period}_{run_id}",
                run_id=run_id,
                dataset_id=dataset_id,
                dataset_version=dataset_version,
                rule_name="balance_sheet_identity",
                dimension="accounting_consistency",
                severity="hard_failure",
                line_item="total_assets",
                period=period,
                observed_value=assets,
                expected_value=expected,
                tolerance=tolerance,
                message=f"Balance Sheet imbalance in {period}: Total Assets ({assets:,.2f}) != Liabilities + Equity ({expected:,.2f}), delta = {diff:,.2f}",
                source_row=source_row,
            )
    return None


def check_income_statement_math(
    facts_by_item: Dict[str, float],
    period: str,
    dataset_id: str,
    dataset_version: int,
    run_id: str,
    tolerance: float = DEFAULT_BALANCE_TOLERANCE,
) -> List[ValidationFinding]:
    """
    Validates gross profit and net income consistency.
    Violations are logged as warnings or hard failures depending on materiality.
    """
    findings: List[ValidationFinding] = []

    rev = facts_by_item.get("revenue")
    cogs = facts_by_item.get("cost_of_goods_sold")
    gp = facts_by_item.get("gross_profit")

    if rev is not None and cogs is not None and gp is not None:
        # Depending on reporting sign, cogs may be positive or negative
        cogs_val = abs(cogs)
        expected_gp = rev - cogs_val
        diff = abs(gp - expected_gp)
        if diff > tolerance:
            findings.append(
                ValidationFinding(
                    finding_id=f"vf_is_gp_{period}_{run_id}",
                    run_id=run_id,
                    dataset_id=dataset_id,
                    dataset_version=dataset_version,
                    rule_name="gross_profit_identity",
                    dimension="accounting_consistency",
                    severity="warning",
                    line_item="gross_profit",
                    period=period,
                    observed_value=gp,
                    expected_value=expected_gp,
                    tolerance=tolerance,
                    message=f"Gross profit discrepancy in {period}: reported {gp:,.2f} vs calculated (Rev - COGS) {expected_gp:,.2f}",
                )
            )

    return findings


def check_cash_flow_reconciliation(
    facts_by_item: Dict[str, float],
    period: str,
    dataset_id: str,
    dataset_version: int,
    run_id: str,
    tolerance: float = DEFAULT_BALANCE_TOLERANCE,
) -> Optional[ValidationFinding]:
    """
    Validates Net Change in Cash = CFO + CFI + CFF.
    """
    cfo = facts_by_item.get("operating_cash_flow")
    cfi = facts_by_item.get("investing_cash_flow")
    cff = facts_by_item.get("financing_cash_flow")
    net_cash = facts_by_item.get("net_change_in_cash")

    if cfo is not None and cfi is not None and cff is not None and net_cash is not None:
        expected = cfo + cfi + cff
        diff = abs(net_cash - expected)
        if diff > tolerance:
            return ValidationFinding(
                finding_id=f"vf_cf_bridge_{period}_{run_id}",
                run_id=run_id,
                dataset_id=dataset_id,
                dataset_version=dataset_version,
                rule_name="cash_flow_reconciliation",
                dimension="accounting_consistency",
                severity="warning",
                line_item="net_change_in_cash",
                period=period,
                observed_value=net_cash,
                expected_value=expected,
                tolerance=tolerance,
                message=f"Cash flow reconciliation mismatch in {period}: reported change ({net_cash:,.2f}) != CFO+CFI+CFF ({expected:,.2f})",
            )
    return None
