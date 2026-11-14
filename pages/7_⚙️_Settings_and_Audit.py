"""
Phase 8: Settings and Audit UI Page (Streamlit)
Displays database connection metadata, active application configurations,
secret redactions, and comprehensive audit timeline of platform operations.
"""

import json
import sys
from pathlib import Path
import streamlit as st
import pandas as pd

# Setup python path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database.connection import db_manager
from app.core.config import settings
from app.ui.components import load_terminal_theme, render_disclaimer

st.set_page_config(page_title="Platform Audit & Settings", layout="wide", page_icon="⚙️")
load_terminal_theme()

st.title("⚙️ Platform Settings & Audit Trail")
st.caption("System health, redacted runtime configurations, and immutable audit logs")

db_conn = db_manager.get_connection()

tabs = st.tabs(["🔒 System & Configuration", "📜 Audit Log & Provenance"])

with tabs[0]:
    st.subheader("Runtime Environment & Safeguards")
    c1, c2, c3 = st.columns(3)
    c1.metric("Database Mode", "DuckDB (File-Backed Warehouse)")
    c2.metric("Environment", getattr(settings, "APP_ENV", "local").upper())
    c3.metric("Arithmetic Guarantee", "100% Deterministic Python")

    st.markdown("---")
    st.subheader("Configured Properties (Secrets Redacted)")

    groq_key = getattr(settings, "GROQ_API_KEY", None)
    config_data = {
        "Configuration Key": [
            "APP_ENV",
            "LOG_LEVEL",
            "DB_PATH",
            "GROQ_MODEL",
            "GROQ_API_KEY",
            "MANDATORY_DISCLAIMER_ENABLED",
        ],
        "Configured Value": [
            str(getattr(settings, "APP_ENV", "local")),
            str(getattr(settings, "LOG_LEVEL", "INFO")),
            str(getattr(settings, "DB_PATH", "database/financial_warehouse.duckdb")),
            str(getattr(settings, "GROQ_MODEL", "llama-3.3-70b-versatile")),
            "[REDACTED]" if groq_key else "Not Configured (Deterministic Fallback Active)",
            "Active (Research & Educational Use Only)",
        ],
    }
    st.table(pd.DataFrame(config_data))

with tabs[1]:
    st.subheader("System Audit Timeline")

    rows = db_conn.execute(
        """
        SELECT event_id, timestamp, actor_id, action, target_type, target_id, details
        FROM audit_events
        ORDER BY timestamp DESC
        LIMIT 100
        """
    ).fetchall()

    if not rows:
        st.info("No audit events recorded yet.")
    else:
        st.write(f"Showing last {len(rows)} events:")

        events = []
        audit_rows = []
        for r in rows:
            parsed_details = json.loads(r[6]) if r[6] else {}
            events.append({
                "event_id": r[0],
                "timestamp": str(r[1]),
                "actor_id": r[2],
                "action": r[3],
                "target_type": r[4],
                "target_id": r[5],
                "details": parsed_details,
            })
            audit_rows.append({
                "Timestamp": r[1],
                "User": r[2],
                "Action": r[3],
                "Entity Type": r[4],
                "Entity ID": r[5],
            })

        st.dataframe(pd.DataFrame(audit_rows), width="stretch")

        with st.expander("Inspect Raw Audit Event Details"):
            st.json(events)

render_disclaimer()