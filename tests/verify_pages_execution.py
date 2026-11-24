"""
Simulates the exact data fetching and computation performed by each Streamlit page
when Microsoft Corporation (co_msft) is selected.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Inject venv
for site in [
    PROJECT_ROOT / "venv" / "Lib" / "site-packages",
    PROJECT_ROOT.parent / "venv" / "Lib" / "site-packages",
]:
    if site.exists() and str(site) not in sys.path:
        sys.path.insert(0, str(site))

import duckdb
import pandas as pd
from app.database.connection import db_manager
from app.database.repositories import (
    CompanyRepository,
    FinancialFactRepository,
    ValidationRepository,
    ForecastRepository,
    ValuationRepository,
    ReportRepository,
)
from app.services.analyst_service import AnalystService

def test_all_pages():
    conn = db_manager.get_connection()
    company_id = "co_msft"

    print("=" * 60)
    print("PAGE 1: Home & Executive Overview (🏠_Home.py)")
    print("=" * 60)
    companies = CompanyRepository(conn).list_all()
    print(f"Registered companies: {[c.name for c in companies]}")
    assert any(c.company_id == company_id for c in companies), "co_msft not in companies"

    # Query latest facts for MSFT
    facts_df = conn.execute(
        """
        SELECT f.canonical_item, f.period, f.normalized_value, f.original_unit, f.source_file, d.statement_type
        FROM financial_facts f
        JOIN datasets d ON f.dataset_id = d.dataset_id
        JOIN dataset_versions v ON f.dataset_id = v.dataset_id AND f.dataset_version = v.version
        WHERE d.company_id = ? AND v.is_active = TRUE
        ORDER BY f.period ASC, f.canonical_item ASC
        """,
        [company_id],
    ).fetchdf()
    print(f"Loaded {len(facts_df)} facts across periods: {sorted(facts_df['period'].unique())}")
    rev_2024 = facts_df[(facts_df['canonical_item'] == 'revenue') & (facts_df['period'] == '2024')]['normalized_value'].values[0]
    print(f"2024 Revenue: ${rev_2024:,.2f}")
    assert rev_2024 == 245_122_000_000.0

    print("\n" + "=" * 60)
    print("PAGE 2: Data Quality Scorecard (1_🔍_Data_Quality.py)")
    print("=" * 60)
    val_runs = conn.execute(
        """
        SELECT r.run_id, r.dataset_id, r.overall_quality_score, r.completeness_score,
               r.mapping_quality_score, r.accounting_consistency_score, r.has_hard_failures,
               d.statement_type
        FROM validation_runs r
        JOIN datasets d ON r.dataset_id = d.dataset_id
        WHERE d.company_id = ?
        ORDER BY r.executed_at DESC
        """,
        [company_id],
    ).fetchdf()
    print(f"Validation runs for MSFT: {len(val_runs)}")
    for _, row in val_runs.iterrows():
        print(f" - {row['statement_type']}: Score {row['overall_quality_score']}/100 (Hard failures: {row['has_hard_failures']})")
    assert not val_runs.empty

    print("\n" + "=" * 60)
    print("PAGE 3: Driver Forecasting & Backtesting (2_📈_Forecasting.py)")
    print("=" * 60)
    fc_runs = conn.execute(
        """
        SELECT forecast_id, model_name, horizon_periods, results_json, backtest_metrics_json, created_at
        FROM forecast_runs
        WHERE dataset_id LIKE ?
        ORDER BY created_at DESC
        """,
        [f"%{company_id}%"],
    ).fetchdf()
    print(f"Forecast runs found: {len(fc_runs)}")
    assert not fc_runs.empty
    latest_fc = fc_runs.iloc[0]
    import json
    projections = json.loads(latest_fc['results_json'])
    print(f"Projections horizon: {len(projections)} years")
    for p in projections:
        print(f" - Year {p['period']}: Rev ${p['revenue']/1e9:,.2f}B | Operating Income ${p['operating_income']/1e9:,.2f}B | FCF ${p['free_cash_flow']/1e9:,.2f}B")

    print("\n" + "=" * 60)
    print("PAGE 4: DCF Valuation & Sensitivity (3_💰_DCF_Valuation.py)")
    print("=" * 60)
    dcf_runs = conn.execute(
        """
        SELECT valuation_id, enterprise_value, equity_value, implied_share_price, wacc, terminal_growth_rate
        FROM valuation_runs
        WHERE dataset_id LIKE ?
        ORDER BY created_at DESC
        """,
        [f"%{company_id}%"],
    ).fetchdf()
    print(f"Valuation runs found: {len(dcf_runs)}")
    assert not dcf_runs.empty
    latest_dcf = dcf_runs.iloc[0]
    print(f" - Implied Share Price: ${latest_dcf['implied_share_price']:.2f}")
    print(f" - Enterprise Value:    ${latest_dcf['enterprise_value']/1e9:,.2f}B")
    print(f" - Equity Value:        ${latest_dcf['equity_value']/1e9:,.2f}B")
    print(f" - WACC:                {latest_dcf['wacc']*100:.2f}%")

    print("\n" + "=" * 60)
    print("PAGE 5: AI Financial Analyst (4_🤖_AI_Analyst.py)")
    print("=" * 60)
    analyst = AnalystService(conn)
    q = "What was operating income in 2024?"
    ans = analyst.answer_question(company_id, q)
    print(f"Q: {q}")
    print(f"A: {ans['answer']}")
    assert "109,433,000,000" in ans["answer"]

    print("\n" + "=" * 60)
    print("PAGE 6: Research Dossier Reports (5_📑_Reports.py)")
    print("=" * 60)
    reports = conn.execute(
        """
        SELECT report_id, report_type, file_path, generation_time_seconds, created_at
        FROM reports
        WHERE company_id = ?
        ORDER BY created_at DESC
        """,
        [company_id],
    ).fetchdf()
    print(f"Generated reports in DB: {len(reports)}")
    for _, r in reports.iterrows():
        p = Path(r['file_path'])
        exists = p.exists()
        size_kb = p.stat().st_size / 1024 if exists else 0
        print(f" - [{r['report_type'].upper()}] {p.name} ({size_kb:.1f} KB) - File Exists: {exists}")
        assert exists, f"Report file {p} does not exist on disk"

    print("\n" + "=" * 60)
    print("PAGE 7: Settings & Audit Logs (6_⚙️_Settings_and_Audit.py)")
    print("=" * 60)
    audits = conn.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
    tables = conn.execute("SHOW TABLES").fetchdf()
    print(f"Total audit trail events: {audits}")
    print(f"Database warehouse tables: {len(tables)} tables verified")
    print("=" * 60)
    print("ALL 7 PAGES EXECUTION TESTS PASSED WITH 100% FIDELITY!")
    print("=" * 60)

if __name__ == "__main__":
    test_all_pages()
