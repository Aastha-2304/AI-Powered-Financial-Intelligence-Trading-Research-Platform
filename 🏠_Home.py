"""
Unified Home & Financial Statement Ingestion Dashboard
AI-Powered Financial Intelligence Platform

Features:
- Primary Entrypoint: Ingest statements and view comprehensive financial overview
- Statement Upload (CSV / Excel) with fuzzy schema matching & human review
- Automatic entity detection & registration (no hardcoded company)
- Executive KPI Overview, revenue trends, and committed facts table
- Seamless navigation to Data Quality, Forecasting, DCF Valuation, and Reports
"""
import sys
from pathlib import Path

# Add project root and local virtual environment site-packages to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
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
import plotly.express as px
import plotly.graph_objects as go

from app.core.config import settings
from app.database.connection import db_manager
from app.database.repositories import CompanyRepository, FinancialFactRepository, ValuationRepository
from app.services.ingestion_service import IngestionService
from app.ingestion.alias_dictionary import CANONICAL_ALIASES
from app.schemas.financial import Company
from app.schemas.workflow import MappingReviewDecision
from app.ui.components import load_terminal_theme, render_disclaimer, render_sidebar_company_selector

st.set_page_config(
    page_title="Financial Intelligence Platform",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)
load_terminal_theme()

conn = db_manager.get_connection()
selected_company_id, selected_name = render_sidebar_company_selector(conn)
ingestion_service = IngestionService(conn)
comp_repo = CompanyRepository(conn)
fact_repo = FinancialFactRepository(conn)
val_repo = ValuationRepository(conn)

st.title("🏦 Financial Intelligence & Valuation Platform")
st.caption("Automated Data Ingestion, Accounting Validation, Driver Forecasting & Intrinsic DCF Valuation")

# Check if active company has committed facts
facts_df = pd.DataFrame()
if selected_company_id:
    facts_df = conn.execute(
        """
        SELECT f.dataset_id, f.dataset_version, f.statement_type, f.canonical_item,
               f.period, f.original_label, f.original_value, f.normalized_value,
               f.normalized_currency, f.source_file, f.source_row
        FROM financial_facts f
        JOIN datasets d ON f.dataset_id = d.dataset_id
        JOIN dataset_versions v ON f.dataset_id = v.dataset_id AND f.dataset_version = v.version
        WHERE d.company_id = ? AND v.is_active = TRUE
        ORDER BY f.period DESC, f.statement_type, f.canonical_item
        """,
        [selected_company_id]
    ).fetchdf()

# Decide view mode: if no data uploaded yet, emphasize upload directly; if data exists, offer tabs
if facts_df.empty:
    st.info("👋 **No financial data uploaded yet.** Upload a financial statement below or load a test sample to begin your analysis.")
    tab_upload, tab_overview = st.tabs(["📥 Upload & Ingest Statement", "📊 Data Overview (Pending Upload)"])
else:
    tab_overview, tab_upload = st.tabs(["📊 Executive Overview & Analysis", "📥 Ingest Additional Statements"])

# -------------------------------------------------------------------
# TAB: UPLOAD & INGEST STATEMENTS
# -------------------------------------------------------------------
with tab_upload:
    st.subheader("1. Financial Statement Ingestion & Schema Matching")
    st.caption("Upload annual or quarterly Income Statements, Balance Sheets, or Cash Flow Statements (CSV or Excel).")

    # Entity definition for upload
    col_ent1, col_ent2, col_ent3 = st.columns(3)
    with col_ent1:
        upload_company_name = st.text_input(
            "Company / Entity Name",
            value=selected_name if selected_name else "Apple Inc.",
            help="Enter the name of the company reporting these financial statements.",
        )
    with col_ent2:
        upload_ticker = st.text_input(
            "Ticker Symbol (Optional)",
            value="AAPL" if (not selected_name or selected_name == "Apple Inc.") else "",
            placeholder="e.g. AAPL, MSFT, TSLA",
        )
    with col_ent3:
        upload_currency = st.selectbox("Reporting Currency", ["USD", "INR", "EUR", "GBP"], index=0)

    st.markdown("---")
    col_up_file, col_up_sample = st.columns([2, 1])

    with col_up_file:
        uploaded_file = st.file_uploader(
            "Choose a statement file (CSV, XLSX, XLS)",
            type=["csv", "xlsx", "xls"],
            help="Supports standard formats with years/quarters in header columns or row headers.",
        )

    with col_up_sample:
        st.markdown("**⚡ Quick Test Datasets**")
        st.caption("Test the pipeline using benchmark test files:")
        sample_choice = st.selectbox(
            "Select Benchmark Sample",
            ["sample_company_financials.csv (3-Year Standard)", "messy_income.csv (Messy Headers & Brackets)"]
        )
        load_sample = st.button("Load Benchmark Sample", use_container_width=True)

    file_bytes = None
    filename = None

    if load_sample:
        if "sample_company_financials" in sample_choice:
            sample_path = PROJECT_ROOT / "data" / "raw" / "sample_company_financials.csv"
            if sample_path.exists():
                file_bytes = sample_path.read_bytes()
                filename = "sample_company_financials.csv"
        else:
            from tests.fixtures.messy_data import MESSY_INCOME_CSV
            file_bytes = MESSY_INCOME_CSV.encode("utf-8")
            filename = "messy_income.csv"

        st.session_state["home_staged_bytes"] = file_bytes
        st.session_state["home_staged_name"] = filename
    elif uploaded_file is not None:
        file_bytes = uploaded_file.getvalue()
        filename = uploaded_file.name
        st.session_state["home_staged_bytes"] = file_bytes
        st.session_state["home_staged_name"] = filename

    staged_bytes = st.session_state.get("home_staged_bytes")
    staged_name = st.session_state.get("home_staged_name")

    if staged_bytes and staged_name:
        st.success(f"Loaded File: **{staged_name}** ({len(staged_bytes):,} bytes)")

        # Ensure target company exists in database
        target_company_id = f"co_{upload_company_name.lower().replace(' ', '_')[:12]}"
        existing_co = comp_repo.get_by_id(target_company_id)
        if not existing_co:
            comp_repo.create(Company(
                company_id=target_company_id,
                name=upload_company_name,
                ticker=upload_ticker.upper() if upload_ticker else None,
                reporting_currency=upload_currency,
            ))
            st.session_state["active_company_id"] = target_company_id
            st.session_state["active_company_name"] = upload_company_name

        try:
            upload_record, sheets = ingestion_service.process_upload(
                company_id=target_company_id,
                filename=staged_name,
                file_bytes=staged_bytes,
            )

            st.markdown("---")
            st.subheader("2. Review Schema Mapping Proposals")
            st.caption("Fuzzy matching proposals generated via RapidFuzz edit distance and financial alias taxonomy.")

            for s_idx, (sheet_name, stmt_type, df, proposals) in enumerate(sheets):
                st.markdown(f"#### Statement {s_idx + 1}: `{sheet_name or 'Main Sheet'}` — Detected: **`{stmt_type}`**")

                with st.expander("📄 View Raw Spreadsheet Preview", expanded=False):
                    st.dataframe(df.head(5), use_container_width=True)

                canonical_options = ["(Skip / Unmapped)"] + sorted(list(CANONICAL_ALIASES.get(stmt_type, {}).keys()))

                with st.form(key=f"home_mapping_form_{s_idx}"):
                    review_decisions_inputs = []

                    col_h1, col_h2, col_h3, col_h4 = st.columns([3, 3, 2, 2])
                    col_h1.markdown("**Raw File Header**")
                    col_h2.markdown("**Canonical Mapped Item**")
                    col_h3.markdown("**Confidence**")
                    col_h4.markdown("**Match Method**")

                    for p_idx, prop in enumerate(proposals):
                        c1, c2, c3, c4 = st.columns([3, 3, 2, 2])
                        c1.write(f"`{prop.raw_label}`")

                        default_val = prop.proposed_canonical if prop.proposed_canonical in canonical_options else "(Skip / Unmapped)"
                        selected_item = c2.selectbox(
                            label=f"Canonical {p_idx}",
                            options=canonical_options,
                            index=canonical_options.index(default_val),
                            key=f"home_canon_{s_idx}_{p_idx}",
                            label_visibility="collapsed",
                        )

                        conf_pct = f"{prop.confidence * 100:.1f}%"
                        badge_color = "#10B981" if prop.confidence >= 0.85 else "#F59E0B" if prop.confidence >= 0.6 else "#EF4444"
                        c3.markdown(f"<span style='color:{badge_color}; font-weight:bold;'>{conf_pct}</span>", unsafe_allow_html=True)
                        c4.write(prop.match_method)

                        review_decisions_inputs.append((prop.raw_label, selected_item, prop.confidence))

                    st.markdown("<br>", unsafe_allow_html=True)
                    commit_col, reject_col = st.columns([2, 1])
                    with commit_col:
                        commit_btn = st.form_submit_button(
                            "✅ Approve Mappings & Commit to DuckDB",
                            type="primary",
                            use_container_width=True,
                        )
                    with reject_col:
                        reject_btn = st.form_submit_button(
                            "❌ Reject Statement",
                            use_container_width=True,
                        )

                    if commit_btn:
                        decisions = []
                        for raw_l, sel_c, conf in review_decisions_inputs:
                            if sel_c != "(Skip / Unmapped)":
                                decisions.append(
                                    MappingReviewDecision(
                                        review_id=f"rev_{raw_l[:20]}",
                                        upload_id=upload_record.upload_id,
                                        raw_label=raw_l,
                                        canonical_item=sel_c,
                                        statement_type=stmt_type,
                                        decision="approve",
                                        reason="Approved by user in Home ingestion UI",
                                    )
                                )

                        if not decisions:
                            st.error("No valid line items mapped. Select at least one item to commit.")
                        else:
                            version_record = ingestion_service.commit_reviewed_statement(
                                upload_id=upload_record.upload_id,
                                company_id=target_company_id,
                                statement_type=stmt_type,
                                df=df,
                                review_decisions=decisions,
                                source_sheet=sheet_name,
                                source_file=staged_name,
                            )
                            if version_record:
                                st.session_state["active_company_id"] = target_company_id
                                st.session_state["active_company_name"] = upload_company_name
                                st.session_state.pop("home_staged_bytes", None)
                                st.session_state.pop("home_staged_name", None)
                                st.balloons()
                                st.success(f"🎉 Successfully committed {len(decisions)} line items to DuckDB for **{upload_company_name}**!")
                                st.rerun()

                    if reject_btn:
                        st.warning("Statement upload rejected. No facts committed.")

        except Exception as e:
            st.error(f"Error during ingestion processing: {str(e)}")

# -------------------------------------------------------------------
# TAB: EXECUTIVE OVERVIEW & ANALYSIS
# -------------------------------------------------------------------
with tab_overview:
    if facts_df.empty:
        st.markdown("""
        ### Ready to Analyze Financial Data
        1. Switch to the **📥 Upload & Ingest Statement** tab.
        2. Upload a financial statement (or click **Load Benchmark Sample**).
        3. Review and approve the fuzzy schema mappings.
        4. Your executive overview, quality score, forecast, and DCF valuation will populate immediately.
        """)
    else:
        st.subheader(f"Executive Scope: **{selected_name}**")

        # Top KPI Cards
        latest_period = facts_df["period"].iloc[0]
        rev_fact = facts_df[facts_df["canonical_item"] == "revenue"]
        latest_rev = rev_fact["normalized_value"].iloc[0] if not rev_fact.empty else 0.0

        ebit_fact = facts_df[facts_df["canonical_item"] == "operating_income"]
        latest_ebit = ebit_fact["normalized_value"].iloc[0] if not ebit_fact.empty else 0.0

        net_inc_fact = facts_df[facts_df["canonical_item"] == "net_income"]
        latest_net = net_inc_fact["normalized_value"].iloc[0] if not net_inc_fact.empty else 0.0

        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        with kpi1:
            st.metric(f"Revenue ({latest_period})", f"${latest_rev:,.0f}")
        with kpi2:
            st.metric(f"Operating Income ({latest_period})", f"${latest_ebit:,.0f}")
        with kpi3:
            st.metric(f"Net Income ({latest_period})", f"${latest_net:,.0f}")
        with kpi4:
            st.metric("Total Warehouse Facts", f"{len(facts_df):,}")

        st.markdown("---")

        # Charts row: Trends & Quality Gauge
        col_c1, col_c2 = st.columns(2)

        with col_c1:
            st.markdown("##### 📈 Historical Financial Trajectory")
            trend_items = ["revenue", "gross_profit", "operating_income", "net_income"]
            sub_facts = facts_df[facts_df["canonical_item"].isin(trend_items)].copy()
            if not sub_facts.empty:
                fig_trend = px.bar(
                    sub_facts,
                    x="period",
                    y="normalized_value",
                    color="canonical_item",
                    barmode="group",
                    title=f"Core Performance Trends ({selected_name})",
                    labels={"normalized_value": "Amount ($)", "period": "Period", "canonical_item": "Metric"},
                    template="plotly_dark",
                )
                fig_trend.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig_trend, use_container_width=True)
            else:
                st.info("No revenue or income figures committed yet.")

        with col_c2:
            st.markdown("##### 🔍 Data Quality & Accounting Status")
            q_score = conn.execute(
                """
                SELECT vr.overall_quality_score, vr.completeness_score, vr.mapping_quality_score,
                       vr.accounting_consistency_score, vr.anomaly_severity_score
                FROM validation_runs vr
                JOIN datasets d ON vr.dataset_id = d.dataset_id
                WHERE d.company_id = ?
                ORDER BY vr.executed_at DESC LIMIT 1
                """,
                [selected_company_id]
            ).fetchone()

            if q_score:
                fig_gauge = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=q_score[0],
                    number={"suffix": "/100", "font": {"size": 28, "color": "#F8FAFC"}},
                    title={"text": "Overall Quality Confidence", "font": {"size": 15, "color": "#94A3B8"}},
                    gauge={
                        "axis": {"range": [0, 100], "tickcolor": "#64748B"},
                        "bar": {"color": "#38BDF8"},
                        "steps": [
                            {"range": [0, 40], "color": "rgba(239, 68, 68, 0.25)"},
                            {"range": [40, 75], "color": "rgba(245, 158, 11, 0.25)"},
                            {"range": [75, 100], "color": "rgba(16, 185, 129, 0.25)"},
                        ],
                    }
                ))
                fig_gauge.update_layout(paper_bgcolor="rgba(0,0,0,0)", font_color="#F8FAFC", height=300, margin=dict(l=20, r=20, t=30, b=20))
                st.plotly_chart(fig_gauge, use_container_width=True)
            else:
                st.info("Quality audit not run yet. Visit the **Data Quality** page to audit accounting invariants and anomalies.")

        st.markdown("---")
        st.subheader("📑 Normalized Facts Warehouse View")
        st.caption(f"Showing all verified financial facts recorded in DuckDB for {selected_name}:")
        st.dataframe(facts_df, use_container_width=True)

        st.markdown("---")
        st.markdown("##### 🧭 Next Analytical Steps")
        nav_c1, nav_c2, nav_c3, nav_c4 = st.columns(4)
        with nav_c1:
            st.info("🔍 **Data Quality**\n\nRun double-entry checks, Z-score & IQR outlier analysis.")
        with nav_c2:
            st.info("📈 **Forecasting**\n\nGenerate 5-year driver projections and compare against Holt linear.")
        with nav_c3:
            st.info("💰 **DCF Valuation**\n\nCalculate CAPM WACC, Gordon terminal value & 5x5 sensitivity matrix.")
        with nav_c4:
            st.info("📋 **Reports**\n\nExport publication-ready Word (.docx) & PDF research dossiers.")

render_disclaimer()
