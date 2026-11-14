"""
Phase 9: LangGraph Human-in-the-Loop Pipeline State Schema
Defines the state graph schema for statement processing with human checkpoints.
"""

from typing import List, Dict, Any, Optional
from typing_extensions import TypedDict


class HumanReviewProposal(TypedDict):
    """Proposal generated for human analyst inspection during mapping pause."""
    raw_header: str
    suggested_canonical: Optional[str]
    confidence: float
    method: str
    statement_type: str
    sample_values: List[float]


class PipelineState(TypedDict):
    """
    State dictionary flowing through the LangGraph Ingestion & Financial Analysis Pipeline.
    """
    # Identifiers
    company_id: str
    upload_id: str
    user_id: str
    dataset_id: Optional[str]

    # File Parsing Outputs
    file_bytes: Optional[bytes]
    filename: Optional[str]
    sheet_data: Dict[str, Any]  # Statement name -> rows/records

    # Mapping Proposals & Human Decision
    mapping_proposals: List[Dict[str, Any]]
    human_decisions: Optional[List[Dict[str, Any]]]
    review_status: str  # 'PENDING_REVIEW', 'APPROVED', 'REJECTED'

    # Normalization & Quality Outputs
    normalized_facts: List[Dict[str, Any]]
    quality_score: Optional[float]
    hard_failure: bool
    quality_findings: List[Dict[str, Any]]

    # Pipeline Status & Audit
    current_step: str
    is_completed: bool
    error: Optional[str]
