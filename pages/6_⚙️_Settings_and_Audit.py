"""
Page 6: Settings, Model Baselines & Audit Trail
AI-Powered Financial Intelligence Platform

Features:
- Company Baseline Configuration: Custom operational and valuation defaults tailored to company requirements
- Valuation Baselines: CAPM risk-free rate, equity risk premium, beta, tax rate, and terminal growth rate
- Driver Baselines: 5-year revenue trajectory, COGS %, OpEx %, CapEx %, D&A %, and working capital days (DSO, DIO, DPO)
- Validation Thresholds: Accounting identity tolerances, Z-score, and IQR outlier boundaries
- System health, environment safeguards, redacted API keys, and immutable DuckDB audit trail
"""
import json
import sys
import uuid
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
import pandas as pd

from app.database.connection import db_manager
from app.core.config import settings
from app.database.repositories import AuditRepository
from app.schemas.workflow import AuditEvent
from app.ui.components import load_terminal_theme, render_disclaimer, render_sidebar_company_selector

st.set_page_config(page_title="Platform Settings & Baselines", layout="wide", page_icon="⚙️")
load_terminal_theme()

db_conn = db_manager.get_connection()
company_id, company_name = render_sidebar_company_selector(db_conn)
audit_repo = AuditRepository(db_conn)

st.title("⚙️ Platform Settings & Company Baselines")
st.caption("Configure company-specific operational baselines, valuation parameters, and view audit provenance.")

tabs = st.tabs([
    "🏢 Company Baseline Parameters",
    "🔒 System & Runtime Configuration",
    "📜 Audit Log & Provenance",
])

# -------------------------------------------------------------
# TAB 1: COMPANY BASELINE PARAMETERS
# -------------------------------------------------------------
with tabs[0]:
    target_scope = company_name if company_name else "Global Platform Default"
    st.subheader(f"Baseline Requirements Configuration for: **{target_scope}**")
    st.caption("Set custom financial and operational baseline parameters according to the company's industry requirements.")

    # Retrieve existing baseline configuration if available
    cfg_key = f"company_baseline_{company_id}" if company_id else "global_baseline_defaults"
    current_cfg = st.session_state.get(cfg_key, st.session_state.get("global_baseline_defaults", {}))

    with st.form("company_baseline_form"):
        st.markdown("#### 1. Valuation & Cost of Capital Baselines (CAPM / WACC)")
        c_v1, c_v2, c_v3 = st.columns(3)
        with c_v1:
            cfg_rf = st.number_input("Baseline Risk-Free Rate ($R_f$) %", value=float(current_cfg.get("rf", 4.2)), step=0.1)
            cfg_beta = st.number_input("Baseline Equity Beta ($\beta$)", value=float(current_cfg.get("beta", 1.15)), step=0.05)
        with c_v2:
            cfg_erp = st.number_input("Baseline Equity Risk Premium ($ERP$) %", value=float(current_cfg.get("erp", 5.5)), step=0.1)
            cfg_kd = st.number_input("Baseline Pre-Tax Borrowing Rate ($K_d$) %", value=float(current_cfg.get("kd_pretax", 4.75)), step=0.25)
        with c_v3:
            cfg_tax = st.number_input("Baseline Marginal Tax Rate ($t$) %", value=float(current_cfg.get("tax_rate", 21.0)), step=1.0)
            cfg_eq_weight = st.slider("Target Equity Capital Weight %", 10.0, 100.0, float(current_cfg.get("eq_weight", 80.0)), step=5.0)
            cfg_g = st.number_input("Perpetual Terminal Growth Rate ($g$) %", value=float(current_cfg.get("terminal_growth", 2.5)), step=0.1)

        st.markdown("---")
        st.markdown("#### 2. Forecasting & Operational Drivers")
        c_d1, c_d2, c_d3 = st.columns(3)
        with c_d1:
            st.markdown("**Revenue Trajectory (%)**")
            cfg_g1 = st.number_input("Year 1 Growth %", value=float(current_cfg.get("g1", 8.0)), step=0.5)
            cfg_g2 = st.number_input("Year 2 Growth %", value=float(current_cfg.get("g2", 7.0)), step=0.5)
            cfg_g3 = st.number_input("Year 3 Growth %", value=float(current_cfg.get("g3", 6.0)), step=0.5)
            cfg_g4 = st.number_input("Year 4 Growth %", value=float(current_cfg.get("g4", 5.0)), step=0.5)
            cfg_g5 = st.number_input("Year 5 Growth %", value=float(current_cfg.get("g5", 4.0)), step=0.5)

        with c_d2:
            st.markdown("**Margins & Reinvestment**")
            cfg_cogs = st.slider("Baseline COGS (% of Revenue)", 20.0, 90.0, float(current_cfg.get("cogs_pct", 58.0)), step=1.0)
            cfg_opex = st.slider("Baseline OpEx (% of Revenue)", 5.0, 50.0, float(current_cfg.get("opex_pct", 15.0)), step=0.5)
            cfg_capex = st.slider("Baseline CapEx (% of Revenue)", 1.0, 20.0, float(current_cfg.get("capex_pct", 4.5)), step=0.5)
            cfg_da = st.slider("Baseline D&A (% of Revenue)", 1.0, 15.0, float(current_cfg.get("da_pct", 4.0)), step=0.5)

        with c_d3:
            st.markdown("**Working Capital Requirements**")
            cfg_dso = st.number_input("Target DSO (Receivables Days)", value=float(current_cfg.get("dso", 45.0)), step=1.0)
            cfg_dio = st.number_input("Target DIO (Inventory Days)", value=float(current_cfg.get("dio", 35.0)), step=1.0)
            cfg_dpo = st.number_input("Target DPO (Payables Days)", value=float(current_cfg.get("dpo", 40.0)), step=1.0)

        st.markdown("---")
        st.markdown("#### 3. Validation & Anomaly Detection Tolerances")
        c_tol1, c_tol2, c_tol3 = st.columns(3)
        with c_tol1:
            cfg_tol = st.number_input("Double-Entry Imbalance Tolerance ($)", value=float(current_cfg.get("tolerance", 1.0)), step=0.1)
        with c_tol2:
            cfg_z = st.number_input(r"YoY Z-Score Outlier Boundary ($\sigma$)", value=float(current_cfg.get("z_threshold", 3.0)), step=0.5)
        with c_tol3:
            cfg_iqr = st.number_input("IQR Outlier Multiplier", value=float(current_cfg.get("iqr_multiplier", 2.5)), step=0.25)

        st.markdown("<br>", unsafe_allow_html=True)
        save_baseline = st.form_submit_button("💾 Save Company Baseline Requirements", type="primary", use_container_width=True)

        if save_baseline:
            updated_baseline = {
                "rf": cfg_rf,
                "beta": cfg_beta,
                "erp": cfg_erp,
                "kd_pretax": cfg_kd,
                "tax_rate": cfg_tax,
                "eq_weight": cfg_eq_weight,
                "terminal_growth": cfg_g,
                "g1": cfg_g1,
                "g2": cfg_g2,
                "g3": cfg_g3,
                "g4": cfg_g4,
                "g5": cfg_g5,
                "cogs_pct": cfg_cogs,
                "opex_pct": cfg_opex,
                "capex_pct": cfg_capex,
                "da_pct": cfg_da,
                "dso": cfg_dso,
                "dio": cfg_dio,
                "dpo": cfg_dpo,
                "tolerance": cfg_tol,
                "z_threshold": cfg_z,
                "iqr_multiplier": cfg_iqr,
            }

            st.session_state[cfg_key] = updated_baseline
            st.session_state["global_baseline_defaults"] = updated_baseline

            # Record event in audit table
            audit_repo.record_event(
                AuditEvent(
                    event_id=f"ev_cfg_{uuid.uuid4().hex[:10]}",
                    actor_id="analyst",
                    action="company_baseline_updated",
                    target_type="company",
                    target_id=company_id or "global",
                    details=updated_baseline,
                )
            )

            st.success(f"✅ Baseline parameters successfully saved for **{target_scope}**! Projections and valuations will default to these parameters.")

# -------------------------------------------------------------
# TAB 2: SYSTEM & RUNTIME CONFIGURATION
# -------------------------------------------------------------
with tabs[1]:
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

# -------------------------------------------------------------
# TAB 3: AUDIT TIMELINE
# -------------------------------------------------------------
with tabs[2]:
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

        st.dataframe(pd.DataFrame(audit_rows), use_container_width=True)

        with st.expander("Inspect Raw Audit Event Details"):
            st.json(events)

render_disclaimer()
