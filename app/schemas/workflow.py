"""
Workflow, approval, and audit event schemas.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class MappingProposal(BaseModel):
    """Proposed mapping for a single extracted raw header."""
    raw_label: str
    proposed_canonical: Optional[str] = None
    statement_type: str
    confidence: float
    method: str = "fuzzy"  # alias, fuzzy, llm_suggestion
    alternatives: List[str] = []


class MappingReviewDecision(BaseModel):
    """Decision submitted by human reviewer for an individual mapping."""
    review_id: str
    upload_id: str
    raw_label: str
    canonical_item: Optional[str]
    statement_type: str
    decision: str  # approve, correct, reject, unknown
    reviewer_id: str = "usr_local_analyst"
    reason: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class WorkflowRun(BaseModel):
    """Business run tracking an end-to-end operation."""
    workflow_id: str
    thread_id: str
    operation: str  # ingestion, validation, forecasting, valuation, reporting
    status: str = Field(default="queued")  # queued, running, waiting_for_approval, completed, failed, cancelled
    current_stage: str = "initial"
    warnings: List[str] = []
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AuditEvent(BaseModel):
    """Audit log entry capturing state mutations and business decisions."""
    event_id: str
    actor_id: str
    action: str  # file_uploaded, mapping_reviewed, dataset_committed, forecast_run, report_generated
    target_type: str  # upload, dataset, mapping, valuation
    target_id: str
    details: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
