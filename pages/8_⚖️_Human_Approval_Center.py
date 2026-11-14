"""
Phase 9: Human-in-the-Loop Approval Center UI Page (Streamlit)
Connects to the FastAPI backend and LangGraph state checkpoints to review,
inspect, and resume interrupted pipelines with human approval.
"""

import sys
from pathlib import Path
import streamlit as st
import pandas as pd
import requests

# Setup python path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.ui.components import load_terminal_theme, render_disclaimer

st.set_page_config(page_title="Human Approval Center", layout="wide", page_icon="⚖️")
load_terminal_theme()

st.title("⚖️ Human-in-the-Loop Approval Center")
st.caption("LangGraph StateGraph checkpoints, schema interrupts, and auditable resume decisions")

API_BASE = "[http://127.0.0.1:8000](http://127.0.0.1:8000)"

st.markdown("""
This center monitors **LangGraph StateGraph Checkpoints**. When fuzzy schema matching confidence
is below strict thresholds or requires explicit sign-off, the pipeline executes an `interrupt()`,
pausing in SQLite until an authorized analyst reviews proposals and submits a `Command(resume=...)`.
""")

col_left, col_right = st.columns([1, 1])

with col_left:
    st.subheader("1. Inspect Pipeline Thread")
    thread_id = st.text_input("Enter Thread ID", value="thread_CMP_AAPL_UPL_001")
    check_btn = st.button("Fetch Checkpoint State", type="primary")

with col_right:
    st.subheader("2. Fast Simulated Test Pipeline")
    if st.button("Trigger Test Ingestion Workflow"):
        sample_payload = {
            "company_id": "CMP_AAPL",
            "upload_id": "UPL_001",
            "user_id": "ANALYST_01",
            "sheet_data": {
                "income_statement": [
                    {"period": "2023", "Total Revenues": 1000.0, "Operating Cost": 600.0, "Net Earnings": 150.0}
                ],
                "balance_sheet": [
                    {"period": "2023", "Total Assets": 2500.0, "Total Liabilities": 1500.0, "Shareholders Equity": 1000.0}
                ],
            },
        }
        try:
            resp = requests.post(f"{API_BASE}/api/v1/pipeline/start", json=sample_payload, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                st.success(f"Pipeline started and interrupted at human review! Thread: `{data['thread_id']}`")
                thread_id = data["thread_id"]
            else:
                st.error(f"Backend error: {resp.text}")
        except Exception:
            st.warning(f"Could not reach FastAPI backend at {API_BASE}. Start backend using `uvicorn app.api.server:app --port 8000`.")

if check_btn or thread_id:
    try:
        res = requests.get(f"{API_BASE}/api/v1/pipeline/{thread_id}/state", timeout=3)
        if res.status_code == 200:
            state_data = res.json()
            values = state_data.get("values", {})
            proposals = values.get("mapping_proposals", [])
            current_step = values.get("current_step", "UNKNOWN")

            st.markdown("---")
            st.subheader(f"Current State: `{current_step}`")

            if proposals and current_step == "AWAITING_HUMAN_APPROVAL":
                st.info("The pipeline is currently PAUSED at `human_review_node`. Review the proposals below:")

                df_proposals = pd.DataFrame(proposals)
                st.dataframe(df_proposals[["raw_header", "statement_type", "suggested_canonical", "confidence", "method"]], width="stretch")

                c_a, c_b = st.columns(2)
                with c_a:
                    if st.button("✅ Approve & Resume Pipeline", type="primary", width="stretch"):
                        resume_payload = {
                            "decisions": [
                                {"raw_header": p["raw_header"], "user_selected": p["suggested_canonical"], "confidence": p["confidence"]}
                                for p in proposals
                            ],
                            "status": "APPROVED",
                            "reviewer_notes": "Analyst verified canonical items.",
                        }
                        r_res = requests.post(f"{API_BASE}/api/v1/pipeline/{thread_id}/resume", json=resume_payload)
                        if r_res.status_code == 200:
                            st.success("Pipeline resumed and completed!")
                            st.json(r_res.json())
                        else:
                            st.error(f"Failed to resume: {r_res.text}")
                with c_b:
                    if st.button("❌ Reject Pipeline", width="stretch"):
                        resume_payload = {
                            "decisions": [],
                            "status": "REJECTED",
                            "reviewer_notes": "Rejected by analyst.",
                        }
                        r_res = requests.post(f"{API_BASE}/api/v1/pipeline/{thread_id}/resume", json=resume_payload)
                        st.warning("Pipeline halted with REJECTED status.")
            elif values.get("is_completed"):
                st.success("Pipeline already completed!")
                st.json({
                    "quality_score": values.get("quality_score"),
                    "hard_failure": values.get("hard_failure"),
                    "facts_count": len(values.get("normalized_facts", [])),
                    "review_status": values.get("review_status"),
                })
        else:
            st.warning(f"No checkpoint found for thread `{thread_id}`.")
    except Exception:
        st.info("FastAPI backend is offline. Run `uvicorn app.api.server:app --port 8000` in a second terminal to test active live endpoints.")

render_disclaimer()