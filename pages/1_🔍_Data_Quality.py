"""
Page 1: Financial Statement Data Quality & Validation Engine
AI-Powered Financial Intelligence Platform

Features:
- Double-entry accounting rule checks (Assets = Liabilities + Equity)
- Income statement and cash flow identity checks
- Statistical anomaly detection (YoY Z-score & IQR outlier analysis)
- 4-Dimensional Quality Scorecard (Completeness, Mapping, Accounting, Anomaly)
- Hard failure cap (max 40/100) when accounting invariants fail
- Exact source row provenance for all flagged findings
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
import pandas as pd
import plotly.graph_objects as go

from app.database.connection import db_manager
from app.database.repositories import FinancialFactRepository, ValidationRepository, DatasetRepository
from app.validation.quality_scoring import QualityScoringEngine
from app.ui.components import load_terminal_theme, render_disclaimer, render_sidebar_company_selector

st.set_page_config(page_title="Data Quality & Anomaly Detection", page_icon="🔍", layout="wide")
load_terminal_theme()

conn = db_manager.get_connection()
company_id, company_name = render_sidebar_company_selector(conn)

fact_repo = FinancialFactRepository(conn)
val_repo = ValidationRepository(conn)
dataset_repo = DatasetRepository(conn)

st.title("🔍 Data Quality & Accounting Verification")
st.caption("Double-Entry Invariants, Anomaly Detection, and 4-Dimension Confidence Scoring")

# Select dataset to validate
datasets = conn.execute(
    """
    SELECT d.dataset_id, d.statement_type, v.version, v.status, v.is_active
    FROM datasets d
    JOIN dataset_versions v ON d.dataset_id = v.dataset_id
    WHERE d.company_id = ? AND v.is_active = TRUE
    ORDER BY d.statement_type, v.version DESC
    """,
    [company_id],
).fetchall()

if not datasets:
    entity_disp = company_name if company_name else "an active entity"
    st.warning(f"No active financial datasets found for **{entity_disp}**. Please upload statements on the **Home** dashboard first.")
    render_disclaimer()
    st.stop()

ds_options = {f"{d[1]} (Version v{d[2]} - {d[0]})": (d[0], d[2], d[1]) for d in datasets}
selected_ds_label = st.selectbox("Select Financial Dataset for Quality Audit", list(ds_options.keys()))
selected_dataset_id, selected_version, selected_stmt_type = ds_options[selected_ds_label]

col_btn1, col_btn2 = st.columns([1, 1])
with col_btn1:
    run_audit = st.button("🚀 Run Comprehensive Quality Audit", type="primary", use_container_width=True)
with col_btn2:
    inject_test_err = st.button("🧪 Simulate Deliberate Accounting Error (Evaluation Test)", use_container_width=True)

# Fetch facts for selected dataset
facts = fact_repo.get_statement_facts(selected_dataset_id, selected_version)

if not facts:
    st.error("No facts recorded for this dataset version.")
    render_disclaimer()
    st.stop()

# Handle simulated error injection for benchmark verification
if inject_test_err:
    st.warning("⚠️ Injected synthetic test imbalance: Modifying Total Assets by +$50,000,000 to test detection engine.")
    # Create modified facts copy with mismatch
    test_facts = []
    for f in facts:
        f_copy = f.model_copy()
        if f_copy.canonical_item == "total_assets":
            f_copy.normalized_value += 50_000_000.0
        test_facts.append(f_copy)
    eval_run, eval_findings = QualityScoringEngine.evaluate_dataset(
        selected_dataset_id, selected_version, test_facts
    )
    st.session_state[f"val_run_{selected_dataset_id}"] = eval_run
    st.session_state[f"val_findings_{selected_dataset_id}"] = eval_findings
elif run_audit or f"val_run_{selected_dataset_id}" not in st.session_state:
    eval_run, eval_findings = QualityScoringEngine.evaluate_dataset(
        selected_dataset_id, selected_version, facts
    )
    val_repo.save_validation_run(eval_run, eval_findings)
    st.session_state[f"val_run_{selected_dataset_id}"] = eval_run
    st.session_state[f"val_findings_{selected_dataset_id}"] = eval_findings

active_run = st.session_state.get(f"val_run_{selected_dataset_id}")
active_findings = st.session_state.get(f"val_findings_{selected_dataset_id}", [])

st.markdown("---")
st.subheader("📊 Quality Scorecard & Dimension Breakdown")

# Display Scorecard Cards & Gauge
c_gauge, c_scores = st.columns([1, 2])

with c_gauge:
    gauge_color = "#10B981" if active_run.overall_quality_score >= 75 else "#F59E0B" if active_run.overall_quality_score >= 40 else "#EF4444"
    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number",
        value=active_run.overall_quality_score,
        number={"suffix": "/100", "font": {"size": 32, "color": "#F8FAFC"}},
        title={"text": "Overall Confidence Score", "font": {"size": 16, "color": "#94A3B8"}},
        gauge={
            "axis": {"range": [0, 100], "tickcolor": "#64748B"},
            "bar": {"color": gauge_color},
            "steps": [
                {"range": [0, 40], "color": "rgba(239, 68, 68, 0.2)"},
                {"range": [40, 75], "color": "rgba(245, 158, 11, 0.2)"},
                {"range": [75, 100], "color": "rgba(16, 185, 129, 0.2)"},
            ],
            "threshold": {
                "line": {"color": "#38BDF8", "width": 4},
                "thickness": 0.75,
                "value": active_run.overall_quality_score,
            },
        }
    ))
    fig_gauge.update_layout(paper_bgcolor="rgba(0,0,0,0)", height=260, margin=dict(l=20, r=20, t=40, b=20))
    st.plotly_chart(fig_gauge, use_container_width=True)

    if active_run.has_hard_failures:
        st.error("🚨 **HARD FAILURE CAP APPLIED**: Accounting invariant failed. Overall score is capped at max 40/100.")
    else:
        st.success("✅ **PASSED**: All core accounting identities verified successfully.")

with c_scores:
    sc1, sc2 = st.columns(2)
    with sc1:
        st.metric("1. Completeness Score (Weight: 30%)", f"{active_run.completeness_score:.1f}%")
        st.caption("Presence of mandatory canonical statement line items.")
        st.metric("3. Accounting Consistency (Weight: 35%)", f"{active_run.accounting_consistency_score:.1f}%")
        st.caption("Balance Sheet and Cash Flow double-entry integrity.")
    with sc2:
        st.metric("2. Mapping Confidence (Weight: 25%)", f"{active_run.mapping_quality_score:.1f}%")
        st.caption("Average algorithmic confidence of accepted line item mappings.")
        st.metric("4. Anomaly Severity (Weight: 10%)", f"{active_run.anomaly_severity_score:.1f}%")
        st.caption("Absence of severe statistical outlier movements (Z-score & IQR).")

st.markdown("---")
st.subheader(f"📋 Detailed Audit Findings ({len(active_findings)} Items)")

if not active_findings:
    st.info("No anomalies or accounting violations detected. Dataset is clean and ready for forecasting.")
else:
    findings_data = []
    for f in active_findings:
        sev_icon = "🔴 Hard Failure" if f.severity == "hard_failure" else "🟡 Warning" if f.severity == "warning" else "🔵 Info"
        findings_data.append({
            "Severity": sev_icon,
            "Dimension": f.dimension.capitalize(),
            "Rule Name": f.rule_name,
            "Period": f.period or "All",
            "Observed": f"{f.observed_value:,.0f}" if f.observed_value is not None else "-",
            "Expected": f"{f.expected_value:,.0f}" if f.expected_value is not None else "-",
            "Message": f.message,
            "Source Row": f.source_row or "Header",
        })

    df_findings = pd.DataFrame(findings_data)
    st.dataframe(df_findings, use_container_width=True)

render_disclaimer()
