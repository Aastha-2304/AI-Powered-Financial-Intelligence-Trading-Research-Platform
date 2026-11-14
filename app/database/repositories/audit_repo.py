"""
Audit and Workflow repository: records lifecycle transitions and audit events.
"""
from typing import List, Optional
import json
import duckdb
from app.schemas.workflow import WorkflowRun, AuditEvent


class AuditRepository:
    def __init__(self, conn: duckdb.DuckDBPyConnection):
        self.conn = conn

    def record_event(self, event: AuditEvent) -> None:
        self.conn.execute(
            """
            INSERT INTO audit_events (event_id, actor_id, action, target_type, target_id, details, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                event.event_id,
                event.actor_id,
                event.action,
                event.target_type,
                event.target_id,
                json.dumps(event.details),
                event.timestamp,
            ],
        )

    def create_workflow_run(self, workflow: WorkflowRun) -> None:
        self.conn.execute(
            """
            INSERT INTO workflow_runs (workflow_id, thread_id, operation, status, current_stage, warnings, error_message, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                workflow.workflow_id,
                workflow.thread_id,
                workflow.operation,
                workflow.status,
                workflow.current_stage,
                json.dumps(workflow.warnings),
                workflow.error_message,
                workflow.created_at,
                workflow.updated_at,
            ],
        )

    def update_workflow_status(
        self,
        workflow_id: str,
        status: str,
        current_stage: str,
        warnings: Optional[List[str]] = None,
        error_message: Optional[str] = None,
    ) -> None:
        self.conn.execute(
            """
            UPDATE workflow_runs
            SET status = ?, current_stage = ?, warnings = ?, error_message = ?, updated_at = CURRENT_TIMESTAMP
            WHERE workflow_id = ?
            """,
            [
                status,
                current_stage,
                json.dumps(warnings or []),
                error_message,
                workflow_id,
            ],
        )

    def get_workflow_run(self, workflow_id: str) -> Optional[WorkflowRun]:
        res = self.conn.execute(
            """
            SELECT workflow_id, thread_id, operation, status, current_stage, warnings, error_message, created_at, updated_at
            FROM workflow_runs
            WHERE workflow_id = ?
            """,
            [workflow_id],
        ).fetchone()
        if not res:
            return None
        return WorkflowRun(
            workflow_id=res[0],
            thread_id=res[1],
            operation=res[2],
            status=res[3],
            current_stage=res[4],
            warnings=json.loads(res[5] or "[]"),
            error_message=res[6],
            created_at=res[7],
            updated_at=res[8],
        )
