"""
Report Generation Coordinator Service:
Fetches saved figures strictly from DuckDB tables (financial_facts, validation_runs, forecast_runs, valuation_runs),
dispatches to WordReportExporter and PDFReportExporter, and logs report metadata into the database.
"""
import time
import uuid
from pathlib import Path
from typing import Dict, Any, Optional
import duckdb

from app.core.config import settings
from app.core.logging import get_logger
from app.reports.word_exporter import WordReportExporter
from app.reports.pdf_exporter import PDFReportExporter
from app.schemas.modeling import ReportRecord
from app.database.connection import db_manager
from app.database.repositories import (
    CompanyRepository,
    FinancialFactRepository,
    ValidationRepository,
    ForecastRepository,
    ValuationRepository,
    ReportRepository,
)

logger = get_logger(__name__)


class ReportService:
    """Service generating traceable DOCX and PDF research reports from database records."""

    def __init__(self, conn: Optional[duckdb.DuckDBPyConnection] = None):
        self.conn = conn or db_manager.get_connection()
        self.comp_repo = CompanyRepository(self.conn)
        self.fact_repo = FinancialFactRepository(self.conn)
        self.val_repo = ValidationRepository(self.conn)
        self.fc_repo = ForecastRepository(self.conn)
        self.dcf_repo = ValuationRepository(self.conn)
        self.report_repo = ReportRepository(self.conn)

    def generate_research_report(
        self,
        company_id: str,
        dataset_id: str,
        dataset_version: int,
        forecast_id: Optional[str] = None,
        valuation_id: Optional[str] = None,
        report_format: str = "docx",  # docx or pdf
    ) -> ReportRecord:
        """
        Coordinates compilation of Word or PDF report.
        All table figures pulled strictly from saved database records.
        """
        start_time = time.time()
        company = self.comp_repo.get_by_id(company_id)
        comp_name = company.name if company else company_id
        currency = company.reporting_currency if company else "USD"

        # 1. Fetch saved historical facts
        facts = self.fact_repo.get_statement_facts(dataset_id, dataset_version)

        # 2. Fetch saved validation run
        quality_run = self.val_repo.get_latest_run(dataset_id, dataset_version)

        # 3. Fetch saved forecast run
        forecast_run = self.fc_repo.get_forecast_run(forecast_id) if forecast_id else None

        # 4. Fetch saved valuation run
        val_run = self.dcf_repo.get_valuation_run(valuation_id) if valuation_id else None

        reports_dir = settings.resolved_reports_dir
        report_id = f"rpt_{uuid.uuid4().hex[:12]}"
        filename = f"{company_id}_{dataset_id}_v{dataset_version}_{report_id}.{report_format}"
        out_path = reports_dir / filename

        if report_format == "docx":
            WordReportExporter.generate_report(
                output_path=out_path,
                company_name=comp_name,
                reporting_currency=currency,
                dataset_id=dataset_id,
                dataset_version=dataset_version,
                historical_facts=facts,
                quality_run=quality_run,
                forecast_run=forecast_run,
                valuation_run=val_run,
            )
        elif report_format == "pdf":
            PDFReportExporter.generate_report(
                output_path=out_path,
                company_name=comp_name,
                reporting_currency=currency,
                dataset_id=dataset_id,
                dataset_version=dataset_version,
                historical_facts=facts,
                quality_run=quality_run,
                forecast_run=forecast_run,
                valuation_run=val_run,
            )
        else:
            raise ValueError(f"Unsupported report format '{report_format}'. Must be 'docx' or 'pdf'.")

        duration = round(time.time() - start_time, 3)
        record = ReportRecord(
            report_id=report_id,
            company_id=company_id,
            dataset_id=dataset_id,
            dataset_version=dataset_version,
            forecast_id=forecast_id,
            valuation_id=valuation_id,
            report_type=report_format,
            file_path=str(out_path),
            generation_time_seconds=duration,
        )
        self.report_repo.save_report_record(record)
        logger.info(
            "Generated %s report %s in %.2f seconds for %s.",
            report_format.upper(), out_path.name, duration, company_id
        )
        return record
