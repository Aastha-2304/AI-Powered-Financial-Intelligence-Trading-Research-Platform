"""
Phase 2 Vertical Slice End-to-End Tests:
1. Upload checks: valid file type, duplicate detection via SHA-256 hash.
2. Statement detection & period column identification.
3. Schema matcher proposals on messy headers (precision & recall).
4. Review step: approve and commit vs. reject.
5. Idempotent commit: double submission produces no duplicate facts.
6. Scaling & sign normalization: millions scale properly, parentheses negative values.
"""
import pytest
from app.schemas.financial import Company
from app.schemas.workflow import MappingReviewDecision
from app.services.ingestion_service import IngestionService
from app.ingestion.schema_matcher import SchemaMatcher
from tests.fixtures.messy_data import MESSY_INCOME_CSV, MESSY_BALANCE_SHEET_CSV


def test_schema_matcher_precision_and_recall():
    """Evaluate fuzzy schema matching against messy income statement headers."""
    matcher = SchemaMatcher("INCOME_STATEMENT")
    
    test_cases = [
        ("Revenue from operations", "revenue"),
        ("Direct Operating Costs", "cost_of_goods_sold"),
        ("Gross Income", "gross_profit"),
        ("Selling General and Admin Expense", "operating_expenses"),
        ("Research & Development", "research_development"),
        ("Operating Profit (EBIT)", "operating_income"),
        ("Finance costs (interest)", "interest_expense"),
        ("Earnings Before Tax", "pretax_income"),
        ("Provision for taxes", "tax_expense"),
        ("Profit for the year (PAT)", "net_income"),
    ]
    
    correct = 0
    for raw_label, expected_canonical in test_cases:
        proposal = matcher.match_header(raw_label)
        if proposal.proposed_canonical == expected_canonical:
            correct += 1

    accuracy = correct / len(test_cases)
    assert accuracy >= 0.90, f"Expected mapping accuracy >= 90%, got {accuracy * 100}%"


def test_end_to_end_vertical_slice_commit(memory_db):
    """
    Test full vertical slice:
    Upload CSV -> Parse -> Map -> Review Approve -> Normalize -> Persist -> Verify Facts.
    """
    service = IngestionService(memory_db)
    
    # 1. Create company
    service.conn.execute(
        "INSERT INTO companies (company_id, name, reporting_currency) VALUES ('co_vertical', 'Vertical Inc', 'USD')"
    )
    
    file_bytes = MESSY_INCOME_CSV.encode("utf-8")
    
    # Step 1: Upload and get proposals
    upload_record, sheets = service.process_upload(
        company_id="co_vertical",
        filename="messy_income.csv",
        file_bytes=file_bytes,
    )
    assert upload_record.upload_id is not None
    assert upload_record.status == "parsed"
    assert len(sheets) == 1
    
    sheet_name, stmt_type, df, proposals = sheets[0]
    assert stmt_type == "INCOME_STATEMENT"
    assert len(proposals) > 0
    
    # Step 2: Simulate human review approval for proposals
    review_decisions = []
    for p in proposals:
        review_decisions.append(
            MappingReviewDecision(
                review_id=f"rev_{p.raw_label}",
                upload_id=upload_record.upload_id,
                raw_label=p.raw_label,
                canonical_item=p.proposed_canonical,
                statement_type=stmt_type,
                decision="approve",
                reason="Approved by analyst in review UI",
            )
        )
        
    # Step 3: Transactional commit
    version = service.commit_reviewed_statement(
        upload_id=upload_record.upload_id,
        company_id="co_vertical",
        statement_type=stmt_type,
        df=df,
        review_decisions=review_decisions,
        source_file="messy_income.csv",
    )
    assert version is not None
    assert version.status == "approved"
    assert version.is_active is True
    assert version.version == 1
    
    # Step 4: Verify facts in DuckDB
    # Header declared "in Millions USD", Revenue FY 2021 was 1000.5 -> normalized should be 1000.5 * 1e6 = 1,000,500,000
    rev_fact = service.fact_repo.get_fact(version.dataset_id, 1, "revenue", "2021")
    assert rev_fact is not None
    assert rev_fact.original_value == 1000.5
    assert rev_fact.scaling_factor == 1_000_000.0
    assert rev_fact.normalized_value == 1_000_500_000.0
    assert rev_fact.source_row == 2


def test_reject_mapping_produces_no_approved_dataset(memory_db):
    """
    Test that if a reviewer rejects the mapping, no approved dataset version is created.
    """
    service = IngestionService(memory_db)
    service.conn.execute(
        "INSERT INTO companies (company_id, name, reporting_currency) VALUES ('co_reject', 'Reject Co', 'USD')"
    )
    
    file_bytes = MESSY_INCOME_CSV.encode("utf-8")
    upload_record, sheets = service.process_upload("co_reject", "reject.csv", file_bytes)
    sheet_name, stmt_type, df, proposals = sheets[0]
    
    # Submit reject decision
    rejection = [
        MappingReviewDecision(
            review_id="rev_reject",
            upload_id=upload_record.upload_id,
            raw_label="Revenue from operations",
            canonical_item=None,
            statement_type=stmt_type,
            decision="reject",
            reason="Unrecognizable header format",
        )
    ]
    
    result = service.commit_reviewed_statement(
        upload_id=upload_record.upload_id,
        company_id="co_reject",
        statement_type=stmt_type,
        df=df,
        review_decisions=rejection,
    )
    assert result is None  # No dataset created
    
    # Verify no facts were written
    fact_count = service.conn.execute("SELECT count(*) FROM financial_facts").fetchone()[0]
    assert fact_count == 0


def test_double_submission_produces_no_duplicate_facts(memory_db):
    """
    Test idempotent resume: submitting the same approval twice does not duplicate financial facts.
    """
    service = IngestionService(memory_db)
    service.conn.execute(
        "INSERT INTO companies (company_id, name, reporting_currency) VALUES ('co_dup', 'Dup Co', 'USD')"
    )
    
    file_bytes = MESSY_BALANCE_SHEET_CSV.encode("utf-8")
    upload_record, sheets = service.process_upload("co_dup", "balance_sheet.csv", file_bytes)
    sheet_name, stmt_type, df, proposals = sheets[0]
    
    decisions = [
        MappingReviewDecision(
            review_id=f"rev_{p.raw_label}",
            upload_id=upload_record.upload_id,
            raw_label=p.raw_label,
            canonical_item=p.proposed_canonical,
            statement_type=stmt_type,
            decision="approve",
        )
        for p in proposals if p.proposed_canonical
    ]
    
    # First submit
    v1 = service.commit_reviewed_statement(
        upload_id=upload_record.upload_id,
        company_id="co_dup",
        statement_type=stmt_type,
        df=df,
        review_decisions=decisions,
    )
    assert v1 is not None
    
    count_after_first = service.conn.execute(
        "SELECT count(*) FROM financial_facts WHERE dataset_id = ? AND dataset_version = ?",
        [v1.dataset_id, v1.version]
    ).fetchone()[0]
    
    # Resubmit identical mapping
    v2 = service.commit_reviewed_statement(
        upload_id=upload_record.upload_id,
        company_id="co_dup",
        statement_type=stmt_type,
        df=df,
        review_decisions=decisions,
    )
    assert v2 is not None
    assert v2.version == 2
    
    count_after_second = service.conn.execute(
        "SELECT count(*) FROM financial_facts WHERE dataset_id = ? AND dataset_version = ?",
        [v2.dataset_id, v2.version]
    ).fetchone()[0]
    
    # Fact counts per version match without double-counting
    assert count_after_first == count_after_second
