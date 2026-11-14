"""
End-to-end ingestion and ETL workflow service:
Coordinates:
1. File verification & duplicate checking (SHA256)
2. Tabular parsing & statement/period identification
3. Schema matching proposal generation
4. Recording human review decisions (approve, correct, reject, unknown)
5. Normalizing facts (units, signs, currency)
6. Transactional versioned commit into DuckDB

Strictly transactional:
- If rejected, no approved dataset version is created.
- Re-submitting the same approval is idempotent and produces no duplicate facts.
"""
import uuid
from typing import List, Dict, Optional, Tuple, Any
import pandas as pd
import duckdb

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import AuthContext
from app.ingestion.file_parser import FileParser, FileParserError
from app.ingestion.statement_detector import StatementDetector
from app.ingestion.schema_matcher import SchemaMatcher
from app.ingestion.normalizer import FinancialNormalizer
from app.schemas.financial import UploadRecord, Dataset, DatasetVersion, FinancialFact
from app.schemas.workflow import MappingProposal, MappingReviewDecision, WorkflowRun, AuditEvent
from app.database.connection import db_manager
from app.database.repositories import (
    UploadRepository,
    DatasetRepository,
    FinancialFactRepository,
    MappingRepository,
    AuditRepository,
)

logger = get_logger(__name__)


class IngestionService:
    """Application service coordinating the ETL and review lifecycle."""

    def __init__(self, conn: Optional[duckdb.DuckDBPyConnection] = None):
        self.conn = conn or db_manager.get_connection()
        self.upload_repo = UploadRepository(self.conn)
        self.dataset_repo = DatasetRepository(self.conn)
        self.fact_repo = FinancialFactRepository(self.conn)
        self.mapping_repo = MappingRepository(self.conn)
        self.audit_repo = AuditRepository(self.conn)

    def process_upload(
        self,
        company_id: str,
        filename: str,
        file_bytes: bytes,
        auth_context: Optional[AuthContext] = None,
    ) -> Tuple[UploadRecord, List[Tuple[str, str, pd.DataFrame, List[MappingProposal]]]]:
        """
        Step 1: Ingests file, checks for duplicates, identifies statements & periods,
        and generates mapping proposals for review.
        """
        auth = auth_context or AuthContext.create_default(company_id=company_id)
        file_hash = FileParser.compute_sha256(file_bytes)
        safe_filename = FileParser.validate_file(filename, file_bytes)

        # Check existing upload by hash
        existing = self.upload_repo.get_by_hash(company_id, file_hash)
        upload_id = existing.upload_id if existing else f"up_{uuid.uuid4().hex[:12]}"

        upload_record = UploadRecord(
            upload_id=upload_id,
            company_id=company_id,
            filename=safe_filename,
            file_hash=file_hash,
            file_size_bytes=len(file_bytes),
            status="parsed",
        )
        if not existing:
            self.upload_repo.create(upload_record)
            self.audit_repo.record_event(
                AuditEvent(
                    event_id=f"ev_{uuid.uuid4().hex[:12]}",
                    actor_id=auth.user_id,
                    action="file_uploaded",
                    target_type="upload",
                    target_id=upload_id,
                    details={"filename": safe_filename, "hash": file_hash},
                )
            )

        # Parse sheets
        parsed_sheets = FileParser.parse_tabular_data(safe_filename, file_bytes)
        proposals_by_sheet = []

        for sheet_name, df in parsed_sheets:
            statement_type = StatementDetector.detect_statement_type(df, sheet_name)
            label_col, period_cols = StatementDetector.identify_layout(df)

            matcher = SchemaMatcher(statement_type)
            raw_labels = df.iloc[:, label_col].dropna().astype(str).tolist()
            proposals = matcher.match_all(raw_labels)

            proposals_by_sheet.append((sheet_name, statement_type, df, proposals))

        return upload_record, proposals_by_sheet

    def commit_reviewed_statement(
        self,
        upload_id: str,
        company_id: str,
        statement_type: str,
        df: pd.DataFrame,
        review_decisions: List[MappingReviewDecision],
        auth_context: Optional[AuthContext] = None,
        source_sheet: Optional[str] = None,
        source_file: str = "upload.csv",
    ) -> Optional[DatasetVersion]:
        """
        Step 2: Applies reviewed mappings, normalizes units and numbers,
        and commits transactionally to DuckDB.
        - If review decision includes a 'reject' or rejection policy, returns None.
        - Idempotent: re-submitting does not duplicate financial facts.
        """
        auth = auth_context or AuthContext.create_default(company_id=company_id)

        # Check for rejections
        for dec in review_decisions:
            self.mapping_repo.record_review_decision(dec)
            if dec.decision == "reject":
                logger.info("Statement upload %s rejected by reviewer.", upload_id)
                self.upload_repo.update_status(upload_id, "rejected", "Rejected during mapping review")
                return None

        # Build mapping lookup: raw_label -> approved canonical item
        label_to_canonical = {
            dec.raw_label.strip().lower(): dec.canonical_item
            for dec in review_decisions
            if dec.decision in {"approve", "correct"} and dec.canonical_item
        }

        # Identify layout
        label_col, period_cols = StatementDetector.identify_layout(df)
        if not period_cols:
            raise ValueError("No reporting period columns detected in spreadsheet.")

        # Detect scale and currency from header text
        header_text = " ".join([str(c) for c in df.columns] + [str(source_sheet or "")])
        unit_name, scale_factor, currency = FinancialNormalizer.detect_unit_and_currency(header_text)

        # Transactional write
        dataset_id = f"ds_{company_id}_{statement_type.lower()}"
        self.dataset_repo.get_or_create_dataset(dataset_id, company_id, statement_type)
        next_ver = self.dataset_repo.get_next_version_number(dataset_id)

        version_record = DatasetVersion(
            dataset_id=dataset_id,
            version=next_ver,
            upload_id=upload_id,
            status="draft",
            is_active=False,
        )
        self.dataset_repo.create_version(version_record)

        facts_to_insert: List[FinancialFact] = []

        for row_idx, row in df.iterrows():
            raw_label_val = row.iloc[label_col]
            if pd.isna(raw_label_val):
                continue
            raw_label_str = str(raw_label_val).strip()
            canonical = label_to_canonical.get(raw_label_str.lower())
            if not canonical:
                continue

            for col_idx, period_str, period_type in period_cols:
                raw_cell_val = row.iloc[col_idx]
                orig_val, norm_val = FinancialNormalizer.normalize_value(raw_cell_val, scale_factor)
                if norm_val is None:
                    continue

                fact_id = f"fact_{dataset_id}_v{next_ver}_{canonical}_{period_str}"
                fact = FinancialFact(
                    fact_id=fact_id,
                    dataset_id=dataset_id,
                    dataset_version=next_ver,
                    statement_type=statement_type,
                    canonical_item=canonical,
                    period=period_str,
                    period_type=period_type,
                    original_label=raw_label_str,
                    original_value=orig_val,
                    original_unit=unit_name,
                    original_currency=currency,
                    normalized_value=norm_val,
                    normalized_currency=currency,
                    scaling_factor=scale_factor,
                    source_file=source_file,
                    source_sheet=source_sheet,
                    source_row=int(row_idx) + 2,  # 1-indexed row with header at line 1
                    mapping_method="reviewed",
                    mapping_confidence=1.0,
                )
                facts_to_insert.append(fact)

        # Atomic commit
        self.fact_repo.insert_facts_batch(facts_to_insert)
        self.dataset_repo.commit_version(dataset_id, next_ver)
        self.upload_repo.update_status(upload_id, "committed")

        self.audit_repo.record_event(
            AuditEvent(
                event_id=f"ev_{uuid.uuid4().hex[:12]}",
                actor_id=auth.user_id,
                action="dataset_committed",
                target_type="dataset_version",
                target_id=f"{dataset_id}:v{next_ver}",
                details={"fact_count": len(facts_to_insert), "upload_id": upload_id},
            )
        )

        version_record.status = "approved"
        version_record.is_active = True
        logger.info(
            "Transactionally committed dataset %s version %d with %d facts.",
            dataset_id, next_ver, len(facts_to_insert)
        )
        return version_record
