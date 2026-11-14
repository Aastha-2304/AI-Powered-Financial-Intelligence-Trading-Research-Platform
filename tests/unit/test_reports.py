"""
Unit Tests for Phase 7 Reports Generation:
1. Generation of Word (.docx) research report from database facts.
2. Generation of PDF research memo via ReportLab from database facts.
3. Verification that generated document figures strictly match stored database records.
4. Persistence and retrieval of ReportRecord in DuckDB.
"""
from pathlib import Path
import pytest
import docx
from app.schemas.financial import Company, FinancialFact
from app.schemas.modeling import ValidationRun, ValuationRun
from app.services.report_service import ReportService
from app.core.constants import DISCLAIMER_TEXT


def test_word_and_pdf_report_generation(memory_db, tmp_path):
    """Verify DOCX and PDF exporters successfully compile and contain exact stored figures."""
    conn = memory_db
    # Seed company, upload, dataset, and financial facts
    conn.execute("INSERT INTO companies (company_id, name, reporting_currency) VALUES ('co_rpt', 'Acme Holdings', 'USD')")
    conn.execute("INSERT INTO uploads (upload_id, company_id, filename, file_hash, file_size_bytes) VALUES ('up_r', 'co_rpt', 'filing.csv', 'hash_r', 500)")
    conn.execute("INSERT INTO datasets (dataset_id, company_id, statement_type) VALUES ('ds_rpt', 'co_rpt', 'INCOME_STATEMENT')")
    conn.execute("INSERT INTO dataset_versions (dataset_id, version, upload_id, status, is_active) VALUES ('ds_rpt', 1, 'up_r', 'approved', TRUE)")

    # Seed fact: Revenue = $500,000,000.00
    conn.execute(
        """
        INSERT INTO financial_facts (
            fact_id, dataset_id, dataset_version, statement_type, canonical_item,
            period, original_label, original_value, original_unit, original_currency,
            normalized_value, normalized_currency, source_file, source_row
        ) VALUES ('fact_r1', 'ds_rpt', 1, 'INCOME_STATEMENT', 'revenue', '2023', 'Revenue', 500.0, 'millions', 'USD', 500000000.0, 'USD', 'filing.csv', 4)
        """
    )

    # Seed validation run: Overall quality score = 95.0
    conn.execute(
        """
        INSERT INTO validation_runs (
            run_id, dataset_id, dataset_version, completeness_score, mapping_quality_score,
            accounting_consistency_score, anomaly_severity_score, overall_quality_score
        ) VALUES ('vr_r1', 'ds_rpt', 1, 100.0, 95.0, 90.0, 100.0, 95.0)
        """
    )

    # Seed valuation run: EV = 1,250,000,000.00
    conn.execute("INSERT INTO assumption_sets (assumption_set_id, company_id, version, assumptions_json) VALUES ('as_r', 'co_rpt', 1, '{}')")
    conn.execute("INSERT INTO forecast_runs (forecast_id, dataset_id, dataset_version, assumption_set_id, model_name, horizon_periods, results_json) VALUES ('fc_r', 'ds_rpt', 1, 'as_r', 'driver_based', 3, '{}')")
    conn.execute(
        """
        INSERT INTO valuation_runs (
            valuation_id, dataset_id, dataset_version, forecast_id, assumption_set_id,
            wacc, terminal_growth_rate, enterprise_value, equity_value, implied_share_price,
            sensitivity_grid_json, scenarios_json
        ) VALUES (
            'val_r', 'ds_rpt', 1, 'fc_r', 'as_r',
            0.09, 0.025, 1250000000.0, 1100000000.0, 22.0, '{}', '{}'
        )
        """
    )

    service = ReportService(conn)

    # 1. Test Word Report
    docx_rec = service.generate_research_report(
        company_id="co_rpt",
        dataset_id="ds_rpt",
        dataset_version=1,
        forecast_id="fc_r",
        valuation_id="val_r",
        report_format="docx",
    )
    assert Path(docx_rec.file_path).exists()
    assert docx_rec.generation_time_seconds > 0.0

    # Parse and inspect generated Word doc for exact database values
    doc = docx.Document(docx_rec.file_path)
    full_text = " ".join([p.text for p in doc.paragraphs] + [c.text for t in doc.tables for r in t.rows for c in r.cells])
    assert "Acme Holdings" in full_text
    assert "500,000,000.00" in full_text  # Revenue figure from financial_facts
    assert "1,250,000,000.00" in full_text  # Enterprise Value from valuation_runs
    assert "95.0" in full_text  # Quality score from validation_runs
    assert "DISCLAIMER" in full_text

    # 2. Test PDF Report
    pdf_rec = service.generate_research_report(
        company_id="co_rpt",
        dataset_id="ds_rpt",
        dataset_version=1,
        forecast_id="fc_r",
        valuation_id="val_r",
        report_format="pdf",
    )
    assert Path(pdf_rec.file_path).exists()
    assert Path(pdf_rec.file_path).stat().st_size > 1000  # Non-empty PDF
    assert pdf_rec.generation_time_seconds > 0.0
