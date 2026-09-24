"""
AI Financial Intelligence Platform -- home page / upload entry point
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent))
sys.path.append(str(Path(__file__).resolve().parent / "etl"))
sys.path.append(str(Path(__file__).resolve().parent / "financial_model"))
sys.path.append(str(Path(__file__).resolve().parent / "common"))

import streamlit as st
import pandas as pd

from etl.extract import extract_file
from etl.transform import map_raw_dataframe, apply_mapping
from etl.validate import run_all_validations, data_quality_score
from etl.load import get_connection, ensure_schema, load_upload
from financial_model.ratios import load_wide_from_db, compute_all_ratios, store_ratios
from styles import load_custom_css, gradient_header, powerbi_kpi
from data_quality import save_field_mapping

st.set_page_config(page_title="AI Financial Intelligence Platform", layout="wide")
load_custom_css()
gradient_header(
    "AI Financial Intelligence Platform",
    "Upload a company's financial statement -- we'll clean, validate, and analyze it.",
)

conn = get_connection()
ensure_schema(conn)

if "pending_upload" not in st.session_state:
    st.session_state.pending_upload = None

st.subheader("1. Upload financial data")
company_name = st.text_input("Company / Entity name", placeholder="e.g. Acme Corp")
uploaded_file = st.file_uploader("Upload financial statement (CSV or Excel)", type=["csv", "xlsx", "xls"])

if uploaded_file is not None and company_name:
    if st.button("Process upload", type="primary"):
        raw_df = extract_file(uploaded_file)
        mapping = map_raw_dataframe(raw_df)
        clean_df = apply_mapping(raw_df, mapping)

        st.session_state.pending_upload = {
            "company_name": company_name,
            "filename": uploaded_file.name,
            "raw_df": raw_df,
            "mapping": mapping,
            "clean_df": clean_df,
        }

if st.session_state.pending_upload:
    data = st.session_state.pending_upload

    st.divider()
    st.subheader("2. Review field mapping")

    exact = data["mapping"][data["mapping"]["match_type"] == "exact"]
    auto = data["mapping"][data["mapping"]["match_type"] == "fuzzy_auto"]
    suggest = data["mapping"][data["mapping"]["match_type"] == "fuzzy_suggest"]
    unmatched = data["mapping"][data["mapping"]["match_type"] == "unmatched"]

    col1, col2, col3, col4 = st.columns(4)
    with col1: powerbi_kpi("Exact Matches", str(len(exact)))
    with col2: powerbi_kpi("Auto-Matched", str(len(auto)))
    with col3: powerbi_kpi("Needs Review", str(len(suggest)))
    with col4: powerbi_kpi("Unmatched", str(len(unmatched)))

    if not suggest.empty:
        st.warning("These fields were fuzzy-matched with moderate confidence -- please review:")
        st.dataframe(suggest[["raw_label", "canonical_field", "confidence"]], use_container_width=True, hide_index=True)

    if not unmatched.empty:
        st.info("These labels could not be matched and will be excluded from analysis:")
        st.dataframe(unmatched[["raw_label"]], use_container_width=True, hide_index=True)

    with st.expander("See full mapping detail"):
        st.dataframe(data["mapping"], use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("3. Validate and confirm")

    issues = run_all_validations(data["clean_df"])
    score = data_quality_score(data["clean_df"], issues)

    col1, col2 = st.columns([1, 3])
    with col1:
        powerbi_kpi("Data Quality Score", f"{score['score']}/100")
    with col2:
        if issues.empty:
            st.success("No validation issues found.")
        else:
            st.dataframe(issues, use_container_width=True, hide_index=True)

    if st.button("Confirm and save to warehouse", type="primary"):
        upload_id = load_upload(conn, data["company_name"], data["filename"],
                                 data["clean_df"], issues, score)
        save_field_mapping(conn, upload_id, data["mapping"])

        wide_df = load_wide_from_db(conn, upload_id)
        ratios_df = compute_all_ratios(wide_df)
        store_ratios(conn, upload_id, data["company_name"], ratios_df)

        st.success(f"Saved! Upload ID: {upload_id}")
        st.info("Go to the sidebar pages to view validation results, ratios, and more.")
        st.session_state.pending_upload = None

st.divider()
st.subheader("Previously uploaded companies")
from shared_utils import get_uploads_list
uploads = get_uploads_list(conn)
if uploads.empty:
    st.info("No uploads yet -- upload a file above to get started.")
else:
    st.dataframe(uploads, use_container_width=True, hide_index=True)