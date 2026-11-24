"""
Page 5: Automated Financial Intelligence & MD&A Report Generation
AI-Powered Financial Intelligence Platform

Features:
- Automated compilation of publication-grade Word (.docx) and PDF dossiers
- Deterministic extraction: All figures pulled strictly from DuckDB tables
- Sections: Executive Summary, Quality Scorecard, Historical Tables, 5-Yr Forecast, DCF Valuation, MD&A Commentary
- One-click file generation and direct browser download
- Full audit lineage recording execution latency and dataset version hashes
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

from app.database.connection import db_manager
from app.services.report_service import ReportService
from app.database.repositories import ReportRepository, DatasetRepository, ForecastRepository, ValuationRepository
from app.ui.components import load_terminal_theme, render_disclaimer, render_sidebar_company_selector

st.set_page_config(page_title="Report Generation", page_icon="📋", layout="wide")
load_terminal_theme()

conn = db_manager.get_connection()
company_id, company_name = render_sidebar_company_selector(conn)

report_service = ReportService(conn)
report_repo = ReportRepository(conn)

st.title("📋 Automated Dossier & MD&A Reports")
st.caption("Generate Institutional-Grade Word (.docx) and PDF Research Reports with Complete Data Lineage")

# Check available datasets for company
datasets = conn.execute(
    """
    SELECT d.dataset_id, d.statement_type, v.version, v.is_active
    FROM datasets d
    JOIN dataset_versions v ON d.dataset_id = v.dataset_id
    WHERE d.company_id = ? AND v.is_active = TRUE
    ORDER BY d.statement_type, v.version DESC
    """,
    [company_id],
).fetchall()

if not datasets:
    entity_disp = company_name if company_name else "an active entity"
    st.warning(f"No active datasets found for **{entity_disp}**. Ingest statements on the **Home** dashboard first.")
    render_disclaimer()
    st.stop()

tab_gen, tab_archive = st.tabs(["📄 Generate New Report", "🗄️ Generated Reports Archive"])

with tab_gen:
    st.subheader(f"Configure Report Scope for {company_name}")

    col_cfg1, col_cfg2 = st.columns(2)

    with col_cfg1:
        ds_map = {f"{d[1]} (v{d[2]} - {d[0]})": (d[0], d[2]) for d in datasets}
        selected_ds_str = st.selectbox("Select Financial Statement Dataset", list(ds_map.keys()))
        target_dataset_id, target_version = ds_map[selected_ds_str]

        # Forecast runs
        forecasts = conn.execute(
            """
            SELECT forecast_id, model_name, created_at
            FROM forecast_runs
            WHERE dataset_id = ? ORDER BY created_at DESC
            """,
            [target_dataset_id]
        ).fetchall()
        fc_options = {"(None / Historical Only)": None}
        for fc in forecasts:
            fc_options[f"{fc[0]} ({fc[1]}) - {fc[2]}"] = fc[0]

        selected_fc_str = st.selectbox("Attach Forecast Projections", list(fc_options.keys()))
        target_forecast_id = fc_options[selected_fc_str]

    with col_cfg2:
        # Valuation runs
        valuations = conn.execute(
            """
            SELECT valuation_id, implied_share_price, enterprise_value, created_at
            FROM valuation_runs
            WHERE dataset_id = ? ORDER BY created_at DESC
            """,
            [target_dataset_id]
        ).fetchall()
        val_options = {"(None / Historical Only)": None}
        for v in valuations:
            val_options[f"{v[0]} (EV: ${v[2]:,.0f}, Share: ${v[1]:.2f}) - {v[3]}"] = v[0]

        selected_val_str = st.selectbox("Attach DCF Valuation & Scenarios", list(val_options.keys()))
        target_valuation_id = val_options[selected_val_str]

        report_fmt = st.radio("Report Output Format", ["docx (Microsoft Word)", "pdf (Adobe PDF)"], horizontal=True)
        fmt_code = "docx" if "docx" in report_fmt else "pdf"

    st.markdown("---")
    st.markdown("##### 🚀 Compile and Export Dossier")

    if st.button(f"Generate Institutional {fmt_code.upper()} Dossier", type="primary", use_container_width=True):
        with st.spinner(f"Compiling {fmt_code.upper()} report from DuckDB facts & valuation models..."):
            try:
                record = report_service.generate_research_report(
                    company_id=company_id,
                    dataset_id=target_dataset_id,
                    dataset_version=target_version,
                    forecast_id=target_forecast_id,
                    valuation_id=target_valuation_id,
                    report_format=fmt_code,
                )

                st.success(f"🎉 Successfully generated **{fmt_code.upper()}** report in **{record.generation_time_seconds:.3f} seconds**!")
                st.caption(f"Artifact Path: `{record.file_path}`")

                file_path = Path(record.file_path)
                if file_path.exists():
                    report_data = file_path.read_bytes()
                    mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document" if fmt_code == "docx" else "application/pdf"
                    st.download_button(
                        label=f"📥 Download {fmt_code.upper()} File ({len(report_data):,} bytes)",
                        data=report_data,
                        file_name=file_path.name,
                        mime=mime_type,
                        type="primary",
                        use_container_width=True,
                    )
            except Exception as e:
                st.error(f"Failed to generate report: {str(e)}")

with tab_archive:
    st.subheader(f"Generated Dossier Archive for {company_name}")
    reports = report_repo.list_reports_for_company(company_id)

    if not reports:
        st.info("No reports generated yet for this entity.")
    else:
        archive_rows = []
        for r in reports:
            p = Path(r.file_path)
            size_kb = f"{p.stat().st_size / 1024:.1f} KB" if p.exists() else "File Deleted"
            archive_rows.append({
                "Report ID": r.report_id,
                "Format": r.report_type.upper(),
                "Dataset ID": r.dataset_id,
                "Version": f"v{r.dataset_version}",
                "Generation Time": f"{r.generation_time_seconds:.3f}s",
                "Size": size_kb,
                "Created At": str(r.created_at),
                "Filename": p.name,
            })
        st.dataframe(pd.DataFrame(archive_rows), use_container_width=True)

render_disclaimer()
