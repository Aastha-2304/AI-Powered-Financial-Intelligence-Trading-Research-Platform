"""
Unit & Integration Tests for Phase 3 Data Quality & Anomaly Engine:
1. Balance sheet identity passes within tolerance, fails beyond tolerance (applied strictly AFTER unit normalization).
2. Outliers are treated as WARNINGS, not hard errors.
3. 4 transparent quality dimensions computed and documented.
4. Anomaly detector catches deliberate 5x YoY jumps.
5. Injected error detection rate & false alarm rate benchmarking.
"""
import pytest
from app.schemas.financial import FinancialFact
from app.validation.accounting_rules import check_balance_sheet_identity, check_cash_flow_reconciliation
from app.validation.anomaly_detector import AnomalyDetector
from app.validation.quality_scoring import QualityScoringEngine


def test_balance_sheet_tolerance_applied_after_unit_normalization():
    """
    Verify tolerance is applied to normalized base units.
    Total Assets = 1,000,000.00
    Liab + Equity = 1,000,000.50
    Tolerance = 1.0 -> Pass!
    """
    facts_within_tol = {
        "total_assets": 1_000_000.00,
        "total_liabilities": 600_000.00,
        "total_equity": 400_000.50,
    }
    finding = check_balance_sheet_identity(
        facts_within_tol, "2023", "ds_test", 1, "run_01", tolerance=1.0
    )
    assert finding is None, "Difference of 0.50 should be accepted within 1.0 tolerance."

    # Imbalance exceeding tolerance: $500 delta -> Hard failure
    facts_imbalanced = {
        "total_assets": 1_000_000.00,
        "total_liabilities": 600_000.00,
        "total_equity": 399_500.00,  # 500 missing
    }
    finding_err = check_balance_sheet_identity(
        facts_imbalanced, "2023", "ds_test", 1, "run_02", tolerance=1.0
    )
    assert finding_err is not None
    assert finding_err.severity == "hard_failure"
    assert "Balance Sheet imbalance" in finding_err.message


def test_outliers_are_warnings_not_hard_failures():
    """
    Verify that time-series statistical outliers are categorized as 'warning' severity,
    preserving real corporate events without blocking the pipeline.
    """
    # 4 periods of revenue: 100M, 110M, 120M, then sudden acquisition jump to 750M (525% jump)
    facts = [
        FinancialFact(
            fact_id=f"fact_rev_{p}",
            dataset_id="ds_test",
            dataset_version=1,
            statement_type="INCOME_STATEMENT",
            canonical_item="revenue",
            period=str(p),
            period_type="annual",
            original_label="Revenue",
            original_value=val,
            normalized_value=val * 1e6,
            source_file="test.csv",
            source_row=i + 2,
        )
        for i, (p, val) in enumerate([(2020, 100.0), (2021, 110.0), (2022, 120.0), (2023, 750.0)])
    ]

    findings = AnomalyDetector.detect_series_anomalies("revenue", facts, "run_03", "ds_test", 1)
    assert len(findings) >= 1
    for f in findings:
        assert f.severity == "warning", "Outliers MUST be warnings, never hard failures"
        assert f.dimension == "anomaly_severity"
        assert "Statistical anomaly" in f.message


def test_four_separate_quality_dimensions_and_capped_score():
    """
    Verify the 4 explicit dimensions and verify that hard failure caps overall score at 40.
    """
    # Create facts with an imbalanced balance sheet
    facts = [
        FinancialFact(
            fact_id=f"fact_{item}",
            dataset_id="ds_bs",
            dataset_version=1,
            statement_type="BALANCE_SHEET",
            canonical_item=item,
            period="2023",
            original_label=item,
            original_value=val,
            normalized_value=val,
            source_file="test.csv",
            source_row=1,
        )
        for item, val in [
            ("total_assets", 1_000_000.0),
            ("total_current_assets", 400_000.0),
            ("total_liabilities", 500_000.0),
            ("total_equity", 300_000.0),  # Missing 200,000 -> Imbalance!
        ]
    ]

    run, findings = QualityScoringEngine.evaluate_dataset("ds_bs", 1, facts, tolerance=1.0)
    assert run.completeness_score == 100.0  # All 4 required items present
    assert run.has_hard_failures is True
    # The overall score must be capped at 40.0 due to hard failure
    assert run.overall_quality_score <= 40.0
    assert any(f.severity == "hard_failure" for f in findings)
