"""
Chatbot -- ask questions about a specific company's financial data
Powered by chatbot.ChatSession (Groq + tool-calling), not keyword matching.
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent))
sys.path.append(str(Path(__file__).resolve().parent.parent / "common"))
sys.path.append(str(Path(__file__).resolve().parent.parent / "ai_agent"))

import streamlit as st

from shared_utils import get_connection, render_upload_selector
from styles import load_custom_css, gradient_header
from chatbot import get_or_create_session

st.set_page_config(page_title="Chatbot", layout="wide")
load_custom_css()
gradient_header("Financial Data Chatbot", "Ask about revenue, ratios, validation, forecasts, or run what-if and stress-test scenarios")

conn = get_connection()
upload_id, company_name = render_upload_selector(conn)

try:
    session = get_or_create_session(st.session_state, conn, upload_id)
except RuntimeError as e:
    st.error(
        f"Chatbot isn't configured yet: {e}\n\n"
        "Make sure GROQ_API_KEY is set in your .env file and python-dotenv "
        "is loaded at the top of app.py."
    )
    st.stop()

# ---------------------------------------------------------------------
# Chat UI
# ---------------------------------------------------------------------

st.subheader("Quick questions")
quick_cols = st.columns(4)
quick_questions = [
    "What's our revenue trend?",
    "What are our key ratios?",
    "What's our data quality score?",
    "Can we survive a 20% revenue shock?",
]

display_key = f"chat_display_{upload_id}"
if display_key not in st.session_state:
    st.session_state[display_key] = []

for col, q in zip(quick_cols, quick_questions):
    if col.button(q, key=f"quick_{q}"):
        st.session_state[display_key].append(("user", q))
        with st.spinner("Thinking..."):
            reply = session.ask(q)
        st.session_state[display_key].append(("assistant", reply))

st.divider()

user_input = st.chat_input(f"Ask about {company_name}'s financials...")
if user_input:
    st.session_state[display_key].append(("user", user_input))
    with st.spinner("Thinking..."):
        reply = session.ask(user_input)
    st.session_state[display_key].append(("assistant", reply))

for role, text in st.session_state[display_key]:
    with st.chat_message(role):
        st.markdown(text)

if not st.session_state[display_key]:
    st.info(
        "Try asking a question above, or click one of the quick-question buttons. "
        "You can also ask what-if questions (\"What happens to net income if revenue "
        "growth is 8%?\") or stress-test questions (\"Can we survive a 30% revenue drop?\")."
    )