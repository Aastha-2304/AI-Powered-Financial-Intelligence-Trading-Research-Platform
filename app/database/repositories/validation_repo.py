"""
Validation Repository: records validation runs and rule findings in DuckDB.
"""
from typing import List, Optional
import duckdb
from app.schemas.modeling import ValidationRun, ValidationFinding


class ValidationRepository:
    """Repository handling persistence of quality scores and detailed findings."""

    def __init__(self, conn: duckdb.DuckDBPyConnection):
        self.conn = conn

    def save_validation_run(
        self,
        run: ValidationRun,
        findings: List[ValidationFinding],
    ) -> None:
        """Saves run summary and all individual findings in active connection."""
        self.conn.execute(
            """
            INSERT INTO validation_runs (
                run_id, dataset_id, dataset_version, completeness_score,
                mapping_quality_score, accounting_consistency_score,
                anomaly_severity_score, overall_quality_score,
                has_hard_failures, total_findings, executed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (run_id) DO NOTHING
            """,
            [
                run.run_id,
                run.dataset_id,
                run.dataset_version,
                run.completeness_score,
                run.mapping_quality_score,
                run.accounting_consistency_score,
                run.anomaly_severity_score,
                run.overall_quality_score,
                run.has_hard_failures,
                run.total_findings,
                run.executed_at,
            ],
        )

        for f in findings:
            self.conn.execute(
                """
                INSERT INTO validation_findings (
                    finding_id, run_id, dataset_id, dataset_version,
                    rule_name, dimension, severity, line_item,
                    period, observed_value, expected_value, tolerance,
                    message, source_row
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (finding_id) DO NOTHING
                """,
                [
                    f.finding_id,
                    f.run_id,
                    f.dataset_id,
                    f.dataset_version,
                    f.rule_name,
                    f.dimension,
                    f.severity,
                    f.line_item,
                    f.period,
                    f.observed_value,
                    f.expected_value,
                    f.tolerance,
                    f.message,
                    f.source_row,
                ],
            )

    def get_latest_run(self, dataset_id: str, dataset_version: int) -> Optional[ValidationRun]:
        res = self.conn.execute(
            """
            SELECT run_id, dataset_id, dataset_version, completeness_score,
                   mapping_quality_score, accounting_consistency_score,
                   anomaly_severity_score, overall_quality_score,
                   has_hard_failures, total_findings, executed_at
            FROM validation_runs
            WHERE dataset_id = ? AND dataset_version = ?
            ORDER BY executed_at DESC LIMIT 1
            """,
            [dataset_id, dataset_version],
        ).fetchone()
        if not res:
            return None
        return ValidationRun(
            run_id=res[0],
            dataset_id=res[1],
            dataset_version=res[2],
            completeness_score=res[3],
            mapping_quality_score=res[4],
            accounting_consistency_score=res[5],
            anomaly_severity_score=res[6],
            overall_quality_score=res[7],
            has_hard_failures=res[8],
            total_findings=res[9],
            executed_at=res[10],
        )

    def get_findings_for_run(self, run_id: str) -> List[ValidationFinding]:
        rows = self.conn.execute(
            """
            SELECT finding_id, run_id, dataset_id, dataset_version,
                   rule_name, dimension, severity, line_item,
                   period, observed_value, expected_value, tolerance,
                   message, source_row
            FROM validation_findings
            WHERE run_id = ?
            ORDER BY severity ASC, line_item ASC
            """,
            [run_id],
        ).fetchall()
        return [
            ValidationFinding(
                finding_id=r[0],
                run_id=r[1],
                dataset_id=r[2],
                dataset_version=r[3],
                rule_name=r[4],
                dimension=r[5],
                severity=r[6],
                line_item=r[7],
                period=r[8],
                observed_value=r[9],
                expected_value=r[10],
                tolerance=r[11],
                message=r[12],
                source_row=r[13],
            )
            for r in rows
        ]
