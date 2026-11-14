"""
Upload and Dataset repository: handles raw upload tracking and dataset version transitions.
"""
from typing import Optional, List
import duckdb
from app.schemas.financial import UploadRecord, Dataset, DatasetVersion


class UploadRepository:
    def __init__(self, conn: duckdb.DuckDBPyConnection):
        self.conn = conn

    def create(self, upload: UploadRecord) -> UploadRecord:
        self.conn.execute(
            """
            INSERT INTO uploads (upload_id, company_id, filename, file_hash, file_size_bytes, status, error_message, uploaded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                upload.upload_id,
                upload.company_id,
                upload.filename,
                upload.file_hash,
                upload.file_size_bytes,
                upload.status,
                upload.error_message,
                upload.uploaded_at,
            ],
        )
        return upload

    def get_by_hash(self, company_id: str, file_hash: str) -> Optional[UploadRecord]:
        res = self.conn.execute(
            """
            SELECT upload_id, company_id, filename, file_hash, file_size_bytes, status, error_message, uploaded_at
            FROM uploads
            WHERE company_id = ? AND file_hash = ?
            ORDER BY uploaded_at DESC LIMIT 1
            """,
            [company_id, file_hash],
        ).fetchone()
        if not res:
            return None
        return UploadRecord(
            upload_id=res[0],
            company_id=res[1],
            filename=res[2],
            file_hash=res[3],
            file_size_bytes=res[4],
            status=res[5],
            error_message=res[6],
            uploaded_at=res[7],
        )

    def update_status(self, upload_id: str, status: str, error_message: Optional[str] = None) -> None:
        self.conn.execute(
            """
            UPDATE uploads
            SET status = ?, error_message = ?
            WHERE upload_id = ?
            """,
            [status, error_message, upload_id],
        )


class DatasetRepository:
    def __init__(self, conn: duckdb.DuckDBPyConnection):
        self.conn = conn

    def get_or_create_dataset(self, dataset_id: str, company_id: str, statement_type: str) -> Dataset:
        self.conn.execute(
            """
            INSERT INTO datasets (dataset_id, company_id, statement_type)
            VALUES (?, ?, ?)
            ON CONFLICT (dataset_id) DO NOTHING
            """,
            [dataset_id, company_id, statement_type],
        )
        return Dataset(dataset_id=dataset_id, company_id=company_id, statement_type=statement_type)

    def create_version(self, version: DatasetVersion) -> DatasetVersion:
        self.conn.execute(
            """
            INSERT INTO dataset_versions (dataset_id, version, upload_id, status, is_active, committed_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                version.dataset_id,
                version.version,
                version.upload_id,
                version.status,
                version.is_active,
                version.committed_at,
                version.created_at,
            ],
        )
        return version

    def get_next_version_number(self, dataset_id: str) -> int:
        res = self.conn.execute(
            "SELECT COALESCE(MAX(version), 0) + 1 FROM dataset_versions WHERE dataset_id = ?",
            [dataset_id],
        ).fetchone()
        return res[0] if res else 1

    def commit_version(self, dataset_id: str, version: int) -> None:
        """Transactionally marks a dataset version approved and active, deactivating prior versions."""
        self.conn.execute(
            """
            UPDATE dataset_versions
            SET is_active = FALSE
            WHERE dataset_id = ?
            """,
            [dataset_id],
        )
        self.conn.execute(
            """
            UPDATE dataset_versions
            SET status = 'approved', is_active = TRUE, committed_at = CURRENT_TIMESTAMP
            WHERE dataset_id = ? AND version = ?
            """,
            [dataset_id, version],
        )
