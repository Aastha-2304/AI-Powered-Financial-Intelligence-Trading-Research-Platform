"""
Phase 9: FastAPI Backend Service with Human-in-the-Loop LangGraph Endpoints
Provides RESTful endpoints for starting ingestion pipelines, inspecting checkpoints,
and submitting human review decisions.
"""

import os
import sqlite3
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, Header, Depends, Query
from pydantic import BaseModel, Field
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from app.workflow.pipeline import create_pipeline_graph
from app.workflow.state import PipelineState
from app.core.constants import DISCLAIMER_TEXT
from app.core.config import get_settings


app = FastAPI(
    title="AI Financial Intelligence API",
    description="Institutional Financial Intelligence Platform API with Human-in-the-Loop LangGraph Workflows.",
    version="1.0.0"
)

# Persistent SQLite Checkpointer for Workflow State
CHECKPOINT_DB = os.path.join(os.path.dirname(__file__), "checkpoints.db")
sqlite_conn = sqlite3.connect(CHECKPOINT_DB, check_same_thread=False)
checkpointer = SqliteSaver(sqlite_conn)
pipeline_graph = create_pipeline_graph(checkpointer=checkpointer)


# Pydantic Request / Response Models
class PipelineStartRequest(BaseModel):
    company_id: str
    upload_id: str
    user_id: str
    sheet_data: Dict[str, Any] = Field(..., description="Dict of statement type to records")


class PipelineStartResponse(BaseModel):
    thread_id: str
    status: str
    current_step: str
    interrupt_payload: Optional[Dict[str, Any]] = None
    disclaimer: str = DISCLAIMER_TEXT


class HumanDecisionItem(BaseModel):
    raw_header: str
    user_selected: Optional[str]
    confidence: Optional[float] = 1.0


class HumanReviewSubmitRequest(BaseModel):
    decisions: List[HumanDecisionItem]
    status: str = "APPROVED"  # 'APPROVED' or 'REJECTED'
    reviewer_notes: Optional[str] = None


class PipelineStatusResponse(BaseModel):
    thread_id: str
    is_completed: bool
    current_step: str
    review_status: str
    quality_score: Optional[float] = None
    hard_failure: Optional[bool] = False
    facts_count: int = 0
    error: Optional[str] = None
    disclaimer: str = DISCLAIMER_TEXT


@app.get("/health")
def health_check():
    """Healthcheck endpoint."""
    return {
        "status": "healthy",
        "service": "AI Financial Intelligence Platform API",
        "disclaimer": DISCLAIMER_TEXT
    }


@app.post("/api/v1/pipeline/start", response_model=PipelineStartResponse)
def start_pipeline(req: PipelineStartRequest):
    """
    Initiates the financial ingestion pipeline.
    The graph executes until reaching the human review interrupt.
    """
    thread_id = f"thread_{req.company_id}_{req.upload_id}"
    config = {"configurable": {"thread_id": thread_id}}

    initial_state: PipelineState = {
        "company_id": req.company_id,
        "upload_id": req.upload_id,
        "user_id": req.user_id,
        "dataset_id": None,
        "file_bytes": None,
        "filename": None,
        "sheet_data": req.sheet_data,
        "mapping_proposals": [],
        "human_decisions": None,
        "review_status": "PENDING_REVIEW",
        "normalized_facts": [],
        "quality_score": None,
        "hard_failure": False,
        "quality_findings": [],
        "current_step": "START",
        "is_completed": False,
        "error": None
    }

    # Run pipeline up to human review interrupt
    interrupt_payload = None
    for event in pipeline_graph.stream(initial_state, config=config):
        if "__interrupt__" in event:
            interrupt_payload = event["__interrupt__"][0].value

    state = pipeline_graph.get_state(config)
    return PipelineStartResponse(
        thread_id=thread_id,
        status="INTERRUPTED" if interrupt_payload else "RUNNING",
        current_step=state.values.get("current_step", "UNKNOWN"),
        interrupt_payload=interrupt_payload
    )


@app.get("/api/v1/pipeline/{thread_id}/state")
def get_pipeline_state(thread_id: str):
    """Fetches the current checkpoint state of the workflow thread."""
    config = {"configurable": {"thread_id": thread_id}}
    state = pipeline_graph.get_state(config)
    if not state or not state.values:
        raise HTTPException(status_code=404, detail="Thread state not found")

    return {
        "thread_id": thread_id,
        "values": state.values,
        "next": state.next,
        "tasks": [t.name for t in state.tasks] if state.tasks else []
    }


@app.post("/api/v1/pipeline/{thread_id}/resume", response_model=PipelineStatusResponse)
def resume_pipeline(thread_id: str, req: HumanReviewSubmitRequest):
    """
    Resumes a paused workflow by providing human analyst review decisions.
    Uses LangGraph Command(resume=...) to advance past the checkpoint.
    """
    config = {"configurable": {"thread_id": thread_id}}
    state = pipeline_graph.get_state(config)
    if not state or not state.values:
        raise HTTPException(status_code=404, detail="Thread not found")

    resume_payload = {
        "decisions": [d.model_dump() for d in req.decisions],
        "status": req.status,
        "notes": req.reviewer_notes
    }

    # Resume the interrupted graph with the human decision Command
    command = Command(resume=resume_payload)
    for _ in pipeline_graph.stream(command, config=config):
        pass

    final_state = pipeline_graph.get_state(config)
    values = final_state.values

    return PipelineStatusResponse(
        thread_id=thread_id,
        is_completed=values.get("is_completed", False),
        current_step=values.get("current_step", "COMPLETED"),
        review_status=values.get("review_status", "UNKNOWN"),
        quality_score=values.get("quality_score"),
        hard_failure=values.get("hard_failure", False),
        facts_count=len(values.get("normalized_facts", [])),
        error=values.get("error")
    )
