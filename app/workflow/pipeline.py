"""
Phase 9: LangGraph Financial Ingestion Workflow with Human Interrupts.
Constructs a StateGraph that pauses at schema mapping review and resumes via Command/checkpoint.
"""

import os
from typing import Dict, Any, List
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt
from langgraph.checkpoint.sqlite import SqliteSaver

from app.workflow.state import PipelineState
from app.ingestion.schema_matcher import SchemaMatcher
from app.ingestion.statement_detector import StatementDetector
from app.ingestion.normalizer import FinancialNormalizer
from app.schemas.financial import FinancialFact
from app.validation.quality_scoring import QualityScoringEngine


# 1. Parsing & Detection Node
def parse_and_detect_node(state: PipelineState) -> Dict[str, Any]:
    """Inspects sheet data, identifies statements, and creates fuzzy schema proposals."""
    proposals: List[Dict[str, Any]] = []

    sheet_data = state.get("sheet_data", {})
    for stmt_name, rows in sheet_data.items():
        if not rows:
            continue
        normalized_stmt = stmt_name.upper()
        if "INCOME" in normalized_stmt:
            normalized_stmt = "INCOME_STATEMENT"
        elif "BALANCE" in normalized_stmt:
            normalized_stmt = "BALANCE_SHEET"
        elif "CASH" in normalized_stmt:
            normalized_stmt = "CASH_FLOW"

        matcher = SchemaMatcher(normalized_stmt)
        headers = list(rows[0].keys()) if isinstance(rows[0], dict) else []
        for h in headers:
            match = matcher.match_header(h)
            proposals.append({
                "raw_header": h,
                "suggested_canonical": match.proposed_canonical,
                "confidence": match.confidence,
                "method": match.method,
                "statement_type": normalized_stmt,
                "user_selected": match.proposed_canonical,  # Default to best suggestion
                "decision": "APPROVED" if match.confidence >= 0.85 else "PENDING"
            })

    return {
        "mapping_proposals": proposals,
        "current_step": "AWAITING_HUMAN_APPROVAL",
        "review_status": "PENDING_REVIEW"
    }


# 2. Human Review Pause Node
def human_review_node(state: PipelineState) -> Dict[str, Any]:
    """
    Interrupts execution to allow a human financial analyst to approve,
    override, or reject the proposed header mappings.
    The interrupt() raises an interruption that can be resumed with human decisions.
    """
    proposals = state.get("mapping_proposals", [])
    
    # Interrupt execution and yield review payload to caller
    review_response = interrupt({
        "action": "REVIEW_SCHEMA_MAPPINGS",
        "company_id": state.get("company_id"),
        "upload_id": state.get("upload_id"),
        "proposals": proposals,
        "message": "Review and verify canonical financial mappings before persisting facts."
    })

    # When resumed, review_response contains human decisions
    decisions = review_response.get("decisions", proposals)
    review_status = review_response.get("status", "APPROVED")

    return {
        "human_decisions": decisions,
        "review_status": review_status,
        "current_step": "NORMALIZATION_AND_VALIDATION"
    }


# 3. Normalization and Quality Validation Node
def normalize_and_validate_node(state: PipelineState) -> Dict[str, Any]:
    """Applies human-approved mappings, normalizes units/signs, and runs quality engine."""
    if state.get("review_status") == "REJECTED":
        return {
            "is_completed": False,
            "error": "Pipeline halted: Human reviewer rejected schema mappings.",
            "current_step": "HALTED"
        }

    decisions = state.get("human_decisions") or state.get("mapping_proposals", [])
    mapping_lookup = {d["raw_header"]: d.get("user_selected") or d.get("suggested_canonical") for d in decisions}

    facts: List[Dict[str, Any]] = []

    sheet_data = state.get("sheet_data", {})
    for stmt_name, rows in sheet_data.items():
        for row_idx, row in enumerate(rows):
            period = str(row.get("period", row.get("Year", "2023")))
            for col, raw_val in row.items():
                if col in ("period", "Year") or col not in mapping_lookup:
                    continue
                canonical = mapping_lookup[col]
                if not canonical:
                    continue

                orig_val, norm_val = FinancialNormalizer.normalize_value(raw_val, scaling_factor=1.0)
                if norm_val is None:
                    continue

                facts.append({
                    "canonical_id": canonical,
                    "period": period,
                    "statement_type": stmt_name,
                    "normalized_value": norm_val,
                    "source_row": row_idx + 2
                })

    financial_facts: List[FinancialFact] = []
    dataset_id = state.get("dataset_id") or "ds_workflow_001"
    upload_id = state.get("upload_id") or "upl_001"
    company_id = state.get("company_id") or "cmp_001"

    for f in facts:
        financial_facts.append(FinancialFact(
            fact_id=f"fact_{len(financial_facts)+1}",
            dataset_id=dataset_id,
            dataset_version=1,
            statement_type=f["statement_type"],
            canonical_item=f["canonical_id"],
            period=f["period"],
            period_type="annual",
            original_label=f["canonical_id"],
            original_value=f["normalized_value"],
            original_unit="ones",
            original_currency="USD",
            normalized_value=f["normalized_value"],
            normalized_currency="USD",
            scaling_factor=1.0,
            source_file="workflow_input.csv",
            source_row=f["source_row"],
            mapping_method="fuzzy",
            mapping_confidence=1.0
        ))

    val_run, findings = QualityScoringEngine.evaluate_dataset(
        dataset_id=dataset_id,
        dataset_version=1,
        facts=financial_facts
    )

    return {
        "normalized_facts": facts,
        "quality_score": val_run.overall_quality_score,
        "hard_failure": val_run.has_hard_failures,
        "quality_findings": [f.model_dump() for f in findings],
        "is_completed": True,
        "current_step": "COMPLETED"
    }


def create_pipeline_graph(checkpointer: Any = None):
    """Builds and compiles the LangGraph Human-in-the-Loop workflow."""
    builder = StateGraph(PipelineState)

    builder.add_node("parse_and_detect", parse_and_detect_node)
    builder.add_node("human_review", human_review_node)
    builder.add_node("normalize_and_validate", normalize_and_validate_node)

    builder.add_edge(START, "parse_and_detect")
    builder.add_edge("parse_and_detect", "human_review")
    builder.add_edge("human_review", "normalize_and_validate")
    builder.add_edge("normalize_and_validate", END)

    return builder.compile(checkpointer=checkpointer)
