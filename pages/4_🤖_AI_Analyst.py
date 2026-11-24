"""
Page 4: Grounded AI Financial Analyst (LLaMA 3.3 70B via Groq)
AI-Powered Financial Intelligence Platform

Features:
- Parameterized typed DuckDB query tools (no unconstrained text-to-SQL)
- Zero LLM arithmetic: All numbers and ratios computed deterministically
- Exact provenance citations (source file, row number, period, version)
- Strict compliance abstention on missing data or investment advice requests
- Full evidence bundle inspection for verifiable auditability
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

for _site in [
    PROJECT_ROOT / "venv" / "Lib" / "site-packages",
    PROJECT_ROOT / ".venv" / "Lib" / "site-packages",
    PROJECT_ROOT.parent / "venv" / "Lib" / "site-packages",
    PROJECT_ROOT.parent / ".venv" / "Lib" / "site-packages",
]:
    if _site.exists() and str(_site) not in sys.path:
        sys.path.insert(0, str(_site))

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database.connection import db_manager
from app.services.analyst_service import AnalystService
from app.core.config import settings
from app.ui.components import load_terminal_theme, render_disclaimer, render_sidebar_company_selector

st.set_page_config(page_title="AI Financial Analyst", page_icon="🤖", layout="wide")
load_terminal_theme()

conn = db_manager.get_connection()
company_id, company_name = render_sidebar_company_selector(conn)
analyst_service = AnalystService(conn)

st.title("🤖 Grounded AI Financial Analyst")
st.caption(f"LLaMA 3.3 70B Inference via Groq API · Grounded in DuckDB Analytical Warehouse · Scope: {company_name or 'Unspecified'}")

# System status badge
has_groq_key = bool(settings.GROQ_API_KEY and settings.GROQ_API_KEY.startswith("gsk_"))
if has_groq_key:
    st.sidebar.success("🟢 LLM Engine: Groq LLaMA 3.3 70B Active")
else:
    st.sidebar.info("🔵 Engine: Deterministic Fallback Active (100% Offline Verifiable)")

# Quick prompt chips
st.markdown("**Suggested Institutional Queries:**")
q_cols = st.columns(3)
sample_queries = [
    "What was the total revenue in 2023?",
    "What was operating profit and margin in 2023?",
    "Show me the revenue growth trend over the last 3 years",
    "What is the calculated DCF Enterprise Value and Equity Value?",
    "What are the bull and bear case scenarios?",
    "Should I buy or sell this stock now?",  # Test compliance rejection
]

selected_query = None
for idx, q_text in enumerate(sample_queries):
    col = q_cols[idx % 3]
    if col.button(f"💬 {q_text}", key=f"q_btn_{idx}", use_container_width=True):
        selected_query = q_text

# Initialize chat session
if "analyst_chat_history" not in st.session_state:
    st.session_state["analyst_chat_history"] = []

# Display conversation history
for msg in st.session_state["analyst_chat_history"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "bundle" in msg and msg["bundle"]:
            with st.expander("🔍 Grounding Evidence Bundle & Source Lineage", expanded=False):
                st.json(msg["bundle"])

# Handle user input (from chat bar or suggested chips)
user_input = st.chat_input("Ask a question about financial statements, margins, valuation, or scenarios...")
active_prompt = selected_query or user_input

if active_prompt:
    # Append user question
    st.session_state["analyst_chat_history"].append({"role": "user", "content": active_prompt})
    with st.chat_message("user"):
        st.markdown(active_prompt)

    # Generate response
    with st.chat_message("assistant"):
        with st.spinner("Querying DuckDB Warehouse & Grounding Answer..."):
            result = analyst_service.answer_question(company_id=company_id, question=active_prompt)
            answer_text = result["answer"]
            evidence_bundle = result["bundle"]

            st.markdown(answer_text)

            with st.expander("🔍 Grounding Evidence Bundle & Source Lineage", expanded=False):
                st.json(evidence_bundle)

            st.session_state["analyst_chat_history"].append({
                "role": "assistant",
                "content": answer_text,
                "bundle": evidence_bundle,
            })

render_disclaimer()
