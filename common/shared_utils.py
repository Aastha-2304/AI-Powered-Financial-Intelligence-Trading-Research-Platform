"""
Shared utilities for all dashboard pages
"""
import sys
from pathlib import Path
import duckdb
import streamlit as st

sys.stdout.reconfigure(encoding="utf-8")

sys.path.append(str(Path(__file__).resolve().parent.parent))
from config import DB_PATH


@st.cache_resource
def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(DB_PATH))


def get_uploads_list(conn):
    """Returns all uploads for the company-selector dropdown, most recent first."""
    return conn.execute("""
        SELECT upload_id, company_name, source_filename, uploaded_at
        FROM uploads ORDER BY uploaded_at DESC
    """).fetchdf()
def render_upload_selector(conn):
    """
    Renders a dropdown to pick which uploaded company/period to view.
    Returns the selected upload_id, or None if no uploads exist yet.
    Call this at the top of every dashboard page.
    """
    uploads = get_uploads_list(conn)
    if uploads.empty:
        st.warning("No data uploaded yet. Go to the home page to upload a financial statement.")
        st.stop()

    uploads["label"] = (uploads["company_name"] + " -- " +
                         uploads["source_filename"] + " (" +
                         uploads["uploaded_at"].astype(str).str.slice(0, 16) + ")")

    selected_label = st.selectbox("Select company / upload", uploads["label"].tolist())
    selected_row = uploads[uploads["label"] == selected_label].iloc[0]
    return selected_row["upload_id"], selected_row["company_name"]