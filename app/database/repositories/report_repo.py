"""
Report repository: tracks generated research reports and documents in DuckDB.
Stores exact dataset, forecast, and valuation version IDs for complete reproducibility.
"""
from typing import Optional, List
import duckdb
from app.schemas.modeling import ReportRecord


class ReportRepository:
    """Repository handling persistence of report metadata and generated artifacts."""

    def __init__(self, conn: duckdb.DuckDBPyConnection):
        self.conn = conn

    def save_report_record(self, report: ReportRecord) -> ReportRecord:
        self.conn.execute(
            """
            INSERT INTO reports (
                report_id, company_id, dataset_id, dataset_version,
                forecast_id, valuation_id, report_type, file_path,
                generation_time_seconds, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (report_id) DO NOTHING
            """,
            [
                report.report_id,
                report.company_id,
                report.dataset_id,
                report.dataset_version,
                report.forecast_id,
                report.valuation_id,
                report.report_type,
                report.file_path,
                report.generation_time_seconds,
                report.created_at,
            ],
        )
        return report

    def get_report_record(self, report_id: str) -> Optional[ReportRecord]:
        res = self.conn.execute(
            """
            SELECT report_id, company_id, dataset_id, dataset_version,
                   forecast_id, valuation_id, report_type, file_path,
                   generation_time_seconds, created_at
            FROM reports
            WHERE report_id = ?
            """,
            [report_id],
        ).fetchone()
        if not res:
            return None
        return ReportRecord(
            report_id=res[0],
            company_id=res[1],
            dataset_id=res[2],
            dataset_version=res[3],
            forecast_id=res[4],
            valuation_id=res[5],
            report_type=res[6],
            file_path=res[7],
            generation_time_seconds=res[8],
            created_at=res[9],
        )

    def list_reports_for_company(self, company_id: str) -> List[ReportRecord]:
        rows = self.conn.execute(
            """
            SELECT report_id, company_id, dataset_id, dataset_version,
                   forecast_id, valuation_id, report_type, file_path,
                   generation_time_seconds, created_at
            FROM reports
            WHERE company_id = ?
            ORDER BY created_at DESC
            """,
            [company_id],
        ).fetchall()
        return [
            ReportRecord(
                report_id=r[0],
                company_id=r[1],
                dataset_id=r[2],
                dataset_version=r[3],
                forecast_id=r[4],
                valuation_id=r[5],
                report_type=r[6],
                file_path=r[7],
                generation_time_seconds=r[8],
                created_at=r[9],
            )
            for r in rows
        ]
