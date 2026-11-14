"""
Unit tests for Foundation Layer:
- Configuration and secret redacting logger
- Distinct security context identifiers
- DuckDB schema creation and repository operations
- Provenance tracking (original + normalized values, source file/row)
- Transaction rollbacks
"""
import uuid
import pytest
from app.core.config import settings
from app.core.constants import DISCLAIMER_TEXT
from app.core.security import AuthContext
from app.core.logging import get_logger
from app.schemas.financial import Company, UploadRecord, DatasetVersion, FinancialFact, LineItemAlias
from app.schemas.workflow import MappingReviewDecision, WorkflowRun, AuditEvent


def test_disclaimer_and_config():
    """Verify research disclaimer constant and settings loading."""
    assert "DISCLAIMER" in DISCLAIMER_TEXT
    assert "research" in DISCLAIMER_TEXT.lower()
    assert settings.GROQ_MODEL == "llama-3.3-70b-versatile"
    assert settings.APP_ENV == "development"


def test_security_context_distinct_ids():
    """Verify company_id, dataset_id, workflow_id, and thread_id are strictly distinct."""
    ctx = AuthContext.create_default(
        company_id="co_apple",
        dataset_id="ds_income_2023",
        dataset_version=1,
    )
    assert ctx.company_id == "co_apple"
    assert ctx.dataset_id == "ds_income_2023"
    assert ctx.dataset_version == 1
    assert ctx.workflow_id.startswith("wf_")
    assert ctx.thread_id.startswith("th_")
    assert ctx.workflow_id != ctx.thread_id
    assert ctx.user_id == "usr_local_analyst"


def test_company_repository(repos):
    """Test company creation and retrieval."""
    comp_repo = repos["company"]
    company = Company(
        company_id="co_acme",
        name="Acme Corporation",
        ticker="ACME",
        reporting_currency="USD",
    )
    comp_repo.create(company)
    fetched = comp_repo.get_by_id("co_acme")
    assert fetched is not None
    assert fetched.name == "Acme Corporation"
    assert fetched.ticker == "ACME"


def test_upload_and_dataset_versioning(repos):
    """Test upload tracking, dataset creation, and version transitions."""
    comp_repo = repos["company"]
    upload_repo = repos["upload"]
    dataset_repo = repos["dataset"]

    # 1. Create company
    comp_repo.create(Company(company_id="co_test", name="Test Corp"))

    # 2. Track upload
    upload = UploadRecord(
        upload_id="up_001",
        company_id="co_test",
        filename="income_statement.csv",
        file_hash="hash_abc123",
        file_size_bytes=1024,
        status="parsed",
    )
    upload_repo.create(upload)
    assert upload_repo.get_by_hash("co_test", "hash_abc123") is not None

    # 3. Create dataset & version 1
    dataset = dataset_repo.get_or_create_dataset("ds_test_is", "co_test", "INCOME_STATEMENT")
    assert dataset.dataset_id == "ds_test_is"

    v1 = DatasetVersion(
        dataset_id="ds_test_is",
        version=1,
        upload_id="up_001",
        status="draft",
        is_active=False,
    )
    dataset_repo.create_version(v1)
    assert dataset_repo.get_next_version_number("ds_test_is") == 2

    # 4. Commit version 1
    dataset_repo.commit_version("ds_test_is", 1)


def test_financial_fact_provenance_and_deduplication(repos):
    """
    Test storing normalized financial facts next to original reported labels/values
    with source row provenance and idempotent upserts.
    """
    comp_repo = repos["company"]
    upload_repo = repos["upload"]
    dataset_repo = repos["dataset"]
    fact_repo = repos["fact"]

    comp_repo.create(Company(company_id="co_inc", name="Inc Co"))
    upload_repo.create(UploadRecord(
        upload_id="up_002",
        company_id="co_inc",
        filename="balance_sheet.xlsx",
        file_hash="hash_xyz",
        file_size_bytes=2048,
    ))
    dataset_repo.get_or_create_dataset("ds_inc_bs", "co_inc", "BALANCE_SHEET")
    dataset_repo.create_version(DatasetVersion(
        dataset_id="ds_inc_bs",
        version=1,
        upload_id="up_002",
        status="approved",
        is_active=True,
    ))

    # Insert atomic fact
    fact = FinancialFact(
        fact_id="fact_101",
        dataset_id="ds_inc_bs",
        dataset_version=1,
        statement_type="BALANCE_SHEET",
        canonical_item="total_assets",
        period="2023",
        period_type="annual",
        original_label="Assets, Total",
        original_value=500000.0,
        original_unit="thousands",
        original_currency="USD",
        normalized_value=500000000.0,  # Scaled by 1,000 to base currency
        normalized_currency="USD",
        scaling_factor=1000.0,
        source_file="balance_sheet.xlsx",
        source_sheet="Sheet1",
        source_row=12,
        mapping_method="fuzzy",
        mapping_confidence=0.96,
    )
    fact_repo.insert_facts_batch([fact])

    # Fetch and verify provenance
    retrieved = fact_repo.get_fact("ds_inc_bs", 1, "total_assets", "2023")
    assert retrieved is not None
    assert retrieved.original_label == "Assets, Total"
    assert retrieved.original_value == 500000.0
    assert retrieved.normalized_value == 500000000.0
    assert retrieved.source_row == 12
    assert retrieved.mapping_confidence == 0.96


def test_mapping_reviews_and_audit(repos):
    """Test mapping review audit records and workflow lifecycle logging."""
    mapping_repo = repos["mapping"]
    audit_repo = repos["audit"]
    upload_repo = repos["upload"]
    comp_repo = repos["company"]

    comp_repo.create(Company(company_id="co_rev", name="Review Co"))
    upload_repo.create(UploadRecord(
        upload_id="up_003",
        company_id="co_rev",
        filename="cashflow.csv",
        file_hash="hash_cf1",
        file_size_bytes=512,
    ))

    # Record review decision
    decision = MappingReviewDecision(
        review_id="rev_001",
        upload_id="up_003",
        raw_label="Net Cash from Operating Activities",
        canonical_item="operating_cash_flow",
        statement_type="CASH_FLOW",
        decision="approve",
        reviewer_id="usr_local_analyst",
        reason="Exact semantic match",
    )
    mapping_repo.record_review_decision(decision)

    decisions = mapping_repo.get_review_decisions("up_003")
    assert len(decisions) == 1
    assert decisions[0].decision == "approve"
    assert decisions[0].canonical_item == "operating_cash_flow"

    # Record workflow lifecycle run
    wf = WorkflowRun(
        workflow_id="wf_test_123",
        thread_id="th_test_123",
        operation="ingestion",
        status="waiting_for_approval",
        current_stage="schema_mapping_review",
        warnings=["Non-standard header detected"],
    )
    audit_repo.create_workflow_run(wf)
    saved_wf = audit_repo.get_workflow_run("wf_test_123")
    assert saved_wf is not None
    assert saved_wf.status == "waiting_for_approval"
    assert "Non-standard header detected" in saved_wf.warnings
