"""
Transparent data quality scoring engine across four explicit dimensions:
1. Completeness: presence of mandatory canonical statement line items.
2. Mapping Quality: average confidence of accepted line item mappings.
3. Accounting Consistency: absence of accounting identity violations (Balance Sheet, Cash Flow).
4. Anomaly Severity: impact and frequency of statistical outlier movements.

Documented formula for overall quality score (0 - 100 scale):
Overall = 0.30 * Completeness + 0.25 * Mapping + 0.35 * Accounting + 0.10 * Anomaly
(If any hard failure exists, overall score is capped at 40 max to prevent false green status).
"""
import uuid
from typing import List, Dict, Set, Tuple
from app.schemas.financial import FinancialFact
from app.schemas.modeling import ValidationFinding, ValidationRun
from app.validation.accounting_rules import (
    check_balance_sheet_identity,
    check_income_statement_math,
    check_cash_flow_reconciliation,
)
from app.validation.anomaly_detector import AnomalyDetector
from app.core.constants import STATEMENT_INCOME, STATEMENT_BALANCE_SHEET, STATEMENT_CASH_FLOW

# Mandatory core items required for meaningful modeling
REQUIRED_ITEMS = {
    STATEMENT_INCOME: {"revenue", "cost_of_goods_sold", "operating_income", "net_income"},
    STATEMENT_BALANCE_SHEET: {"total_assets", "total_current_assets", "total_liabilities", "total_equity"},
    STATEMENT_CASH_FLOW: {"operating_cash_flow"},
}


class QualityScoringEngine:
    """Evaluates datasets and produces structured scores and findings."""

    @classmethod
    def evaluate_dataset(
        cls,
        dataset_id: str,
        dataset_version: int,
        facts: List[FinancialFact],
        tolerance: float = 1.0,
    ) -> Tuple[ValidationRun, List[ValidationFinding]]:
        """
        Executes all accounting checks, ratio plausibility, and anomaly detectors.
        Returns a ValidationRun summary and a list of detailed ValidationFindings.
        """
        run_id = f"vr_{uuid.uuid4().hex[:12]}"
        all_findings: List[ValidationFinding] = []

        if not facts:
            # Empty dataset
            empty_run = ValidationRun(
                run_id=run_id,
                dataset_id=dataset_id,
                dataset_version=dataset_version,
                completeness_score=0.0,
                mapping_quality_score=0.0,
                accounting_consistency_score=0.0,
                anomaly_severity_score=0.0,
                overall_quality_score=0.0,
                has_hard_failures=True,
                total_findings=1,
            )
            empty_finding = ValidationFinding(
                finding_id=f"vf_empty_{run_id}",
                run_id=run_id,
                dataset_id=dataset_id,
                dataset_version=dataset_version,
                rule_name="empty_dataset_check",
                dimension="completeness",
                severity="hard_failure",
                message="Dataset contains 0 committed financial facts.",
            )
            return empty_run, [empty_finding]

        stmt_type = facts[0].statement_type
        periods = sorted(list({f.period for f in facts}))

        # Group facts by period and canonical item
        facts_by_period: Dict[str, Dict[str, float]] = {p: {} for p in periods}
        facts_by_item: Dict[str, List[FinancialFact]] = {}

        total_confidence = 0.0
        for f in facts:
            facts_by_period[f.period][f.canonical_item] = f.normalized_value
            facts_by_item.setdefault(f.canonical_item, []).append(f)
            total_confidence += f.mapping_confidence

        # -------------------------------------------------------------
        # 1. Completeness Score (0 - 100)
        # -------------------------------------------------------------
        required = REQUIRED_ITEMS.get(stmt_type, set())
        present_canonical_items = set(facts_by_item.keys())
        missing_required = required - present_canonical_items

        for item in missing_required:
            all_findings.append(
                ValidationFinding(
                    finding_id=f"vf_miss_{item}_{run_id}",
                    run_id=run_id,
                    dataset_id=dataset_id,
                    dataset_version=dataset_version,
                    rule_name="mandatory_line_item_check",
                    dimension="completeness",
                    severity="warning",
                    line_item=item,
                    message=f"Mandatory statement item '{item}' is missing from {stmt_type}.",
                )
            )

        completeness_ratio = (
            (len(required) - len(missing_required)) / len(required) if required else 1.0
        )
        completeness_score = round(completeness_ratio * 100.0, 1)

        # -------------------------------------------------------------
        # 2. Mapping Quality Score (0 - 100)
        # -------------------------------------------------------------
        avg_confidence = total_confidence / len(facts) if facts else 0.0
        mapping_quality_score = round(avg_confidence * 100.0, 1)

        # -------------------------------------------------------------
        # 3. Accounting Consistency Score (0 - 100)
        # -------------------------------------------------------------
        accounting_deductions = 0.0

        for p in periods:
            p_facts = facts_by_period[p]
            # Balance sheet identity
            if stmt_type == STATEMENT_BALANCE_SHEET:
                bs_finding = check_balance_sheet_identity(
                    p_facts, p, dataset_id, dataset_version, run_id, tolerance
                )
                if bs_finding:
                    all_findings.append(bs_finding)
                    accounting_deductions += 40.0  # Heavy deduction for balance sheet failure

            # Income statement math
            elif stmt_type == STATEMENT_INCOME:
                is_findings = check_income_statement_math(
                    p_facts, p, dataset_id, dataset_version, run_id, tolerance
                )
                for f in is_findings:
                    all_findings.append(f)
                    accounting_deductions += 15.0

            # Cash flow reconciliation
            elif stmt_type == STATEMENT_CASH_FLOW:
                cf_finding = check_cash_flow_reconciliation(
                    p_facts, p, dataset_id, dataset_version, run_id, tolerance
                )
                if cf_finding:
                    all_findings.append(cf_finding)
                    accounting_deductions += 25.0

        accounting_consistency_score = max(0.0, round(100.0 - accounting_deductions, 1))

        # -------------------------------------------------------------
        # 4. Anomaly Severity Score (0 - 100)
        # -------------------------------------------------------------
        anomaly_findings: List[ValidationFinding] = []
        for canonical, item_facts in facts_by_item.items():
            sorted_facts = sorted(item_facts, key=lambda x: x.period)
            anoms = AnomalyDetector.detect_series_anomalies(
                canonical, sorted_facts, run_id, dataset_id, dataset_version
            )
            anomaly_findings.extend(anoms)

        all_findings.extend(anomaly_findings)
        # Deduct 10 points per detected time-series outlier warning
        anomaly_severity_score = max(0.0, round(100.0 - (len(anomaly_findings) * 10.0), 1))

        # -------------------------------------------------------------
        # Overall Quality Score
        # Formula: 0.30 * Comp + 0.25 * Map + 0.35 * Acct + 0.10 * Anom
        # -------------------------------------------------------------
        overall = (
            (0.30 * completeness_score) +
            (0.25 * mapping_quality_score) +
            (0.35 * accounting_consistency_score) +
            (0.10 * anomaly_severity_score)
        )

        has_hard_failures = any(f.severity == "hard_failure" for f in all_findings)
        if has_hard_failures:
            overall = min(overall, 40.0)  # Capped at 40 if hard failure exists

        run_summary = ValidationRun(
            run_id=run_id,
            dataset_id=dataset_id,
            dataset_version=dataset_version,
            completeness_score=completeness_score,
            mapping_quality_score=mapping_quality_score,
            accounting_consistency_score=accounting_consistency_score,
            anomaly_severity_score=anomaly_severity_score,
            overall_quality_score=round(overall, 1),
            has_hard_failures=has_hard_failures,
            total_findings=len(all_findings),
        )

        return run_summary, all_findings
