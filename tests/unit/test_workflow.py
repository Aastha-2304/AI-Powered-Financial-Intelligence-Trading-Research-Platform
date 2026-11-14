"""
Unit & Integration Tests for Phase 9: FastAPI & LangGraph Human-in-the-Loop Workflow.
Verifies StateGraph compilation, interrupt triggers, checkpoint persistence, and resume commands.
"""

import pytest
import sqlite3
import tempfile
import os
from fastapi.testclient import TestClient

from app.workflow.pipeline import create_pipeline_graph
from app.workflow.state import PipelineState
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from app.api.server import app


@pytest.fixture
def temp_checkpointer():
    """Provides a clean temporary SQLite checkpointer for isolated workflow testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    
    conn = sqlite3.connect(db_path, check_same_thread=False)
    saver = SqliteSaver(conn)
    yield saver
    conn.close()
    if os.path.exists(db_path):
        os.remove(db_path)


def test_pipeline_graph_interrupts_at_human_review(temp_checkpointer):
    """Verifies that the LangGraph StateGraph executes until human_review and pauses."""
    graph = create_pipeline_graph(checkpointer=temp_checkpointer)
    thread_id = "test_thread_001"
    config = {"configurable": {"thread_id": thread_id}}

    initial_state: PipelineState = {
        "company_id": "CMP_TEST",
        "upload_id": "UPL_001",
        "user_id": "USER_01",
        "dataset_id": None,
        "file_bytes": None,
        "filename": "test.csv",
        "sheet_data": {
            "income_statement": [
                {"period": "2023", "Total Revenues": 1000.0, "Operating Cost": 650.0}
            ]
        },
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

    # Execute stream and catch interrupt
    interrupted = False
    interrupt_payload = None
    for event in graph.stream(initial_state, config=config):
        if "__interrupt__" in event:
            interrupted = True
            interrupt_payload = event["__interrupt__"][0].value

    assert interrupted is True
    assert interrupt_payload is not None
    assert interrupt_payload["action"] == "REVIEW_SCHEMA_MAPPINGS"
    assert len(interrupt_payload["proposals"]) > 0

    # Inspect persisted checkpoint state
    state = graph.get_state(config)
    assert state.values["current_step"] == "AWAITING_HUMAN_APPROVAL"
    assert state.values["review_status"] == "PENDING_REVIEW"
    assert state.values["is_completed"] is False


def test_pipeline_graph_resumes_with_command(temp_checkpointer):
    """Verifies that the paused graph resumes upon receiving Command(resume=...) and completes."""
    graph = create_pipeline_graph(checkpointer=temp_checkpointer)
    thread_id = "test_thread_resume"
    config = {"configurable": {"thread_id": thread_id}}

    initial_state: PipelineState = {
        "company_id": "CMP_TEST",
        "upload_id": "UPL_002",
        "user_id": "USER_01",
        "dataset_id": None,
        "file_bytes": None,
        "filename": "test.csv",
        "sheet_data": {
            "income_statement": [
                {"period": "2023", "Total Revenues": 1200.0, "Cost of Goods Sold": 700.0}
            ],
            "balance_sheet": [
                {"period": "2023", "Total Assets": 2000.0, "Total Liabilities": 1200.0, "Shareholders Equity": 800.0}
            ]
        },
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

    # Run up to interrupt
    for _ in graph.stream(initial_state, config=config):
        pass

    state_before = graph.get_state(config)
    proposals = state_before.values["mapping_proposals"]

    # Build human decision payload
    human_decisions = [
        {"raw_header": p["raw_header"], "user_selected": p["suggested_canonical"], "confidence": 1.0}
        for p in proposals
    ]

    resume_command = Command(resume={
        "decisions": human_decisions,
        "status": "APPROVED",
        "notes": "Verified by quantitative analyst."
    })

    # Resume the workflow
    for _ in graph.stream(resume_command, config=config):
        pass

    # Assert final completion
    final_state = graph.get_state(config)
    assert final_state.values["is_completed"] is True
    assert final_state.values["current_step"] == "COMPLETED"
    assert final_state.values["review_status"] == "APPROVED"
    assert len(final_state.values["normalized_facts"]) > 0
    assert final_state.values["quality_score"] is not None
    assert final_state.values["hard_failure"] is False


def test_fastapi_endpoints():
    """Tests the full FastAPI RESTful lifecycle: /health, /pipeline/start, /state, and /resume."""
    client = TestClient(app)

    # 1. Healthcheck
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"
    assert "DISCLAIMER" in resp.json()["disclaimer"]

    # 2. Start Pipeline
    start_payload = {
        "company_id": "CMP_API_TEST",
        "upload_id": "UPL_API_001",
        "user_id": "ANALYST_01",
        "sheet_data": {
            "income_statement": [
                {"period": "2023", "Revenues": 500.0, "Operating Expenses": 300.0}
            ]
        }
    }
    r_start = client.post("/api/v1/pipeline/start", json=start_payload)
    assert r_start.status_code == 200
    start_data = r_start.json()
    assert start_data["status"] == "INTERRUPTED"
    assert start_data["interrupt_payload"] is not None
    thread_id = start_data["thread_id"]

    # 3. Get State
    r_state = client.get(f"/api/v1/pipeline/{thread_id}/state")
    assert r_state.status_code == 200
    state_data = r_state.json()
    assert state_data["values"]["current_step"] == "AWAITING_HUMAN_APPROVAL"

    # 4. Resume Pipeline
    proposals = state_data["values"]["mapping_proposals"]
    resume_payload = {
        "decisions": [
            {"raw_header": p["raw_header"], "user_selected": p["suggested_canonical"], "confidence": 1.0}
            for p in proposals
        ],
        "status": "APPROVED",
        "reviewer_notes": "FastAPI integration test approval."
    }
    r_resume = client.post(f"/api/v1/pipeline/{thread_id}/resume", json=resume_payload)
    assert r_resume.status_code == 200
    resume_data = r_resume.json()
    assert resume_data["is_completed"] is True
    assert resume_data["current_step"] == "COMPLETED"
    assert resume_data["review_status"] == "APPROVED"
    assert resume_data["facts_count"] > 0
