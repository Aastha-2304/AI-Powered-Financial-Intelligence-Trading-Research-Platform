"""
Data Quality -- fuzzy-match confidence, validation issues, and lineage
across all companies and drilled into one selected company.
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent))
sys.path.append(str(Path(__file__).resolve().parent.parent / "common"))

import streamlit as st
import pandas as pd
import plotly.express as px

from shared_utils import get_connection, render_upload_selector
from styles import load_custom_css, gradient_header, powerbi_kpi, status_badge
from chart_theme import apply_theme
from data_quality import ensure_mapping_schema, get_field_mapping, get_mapping_summary, get_data_health_across_companies

st.set_page_config(page_title="Data Quality", layout="wide")
load_custom_css()
gradient_header("Data Quality & Lineage", "Fuzzy-match confidence, validation issues, and traceability across every upload")

conn = get_connection()
ensure_mapping_schema(conn)

# ---------------------------------------------------------------------
# Cross-company health overview
# ---------------------------------------------------------------------
st.subheader("1. Data health across all companies")

health = get_data_health_across_companies(conn)
if health.empty:
    st.info("No uploads yet.")
    st.stop()

health["match_rate_pct"] = health.apply(
    lambda r: round(r["fields_matched"] / r["fields_total"] * 100, 1) if r["fields_total"] else None, axis=1
)

has_lineage = health[health["fields_total"] > 0]
no_lineage = health[health["fields_total"] == 0]

if not has_lineage.empty:
    fig = px.scatter(
        has_lineage, x="match_rate_pct", y="quality_score", size="fields_total",
        color="company_name", hover_name="company_name",
        labels={"match_rate_pct": "Field Match Rate (%)", "quality_score": "Quality Score"},
    )
    fig.update_layout(showlegend=True)
    st.plotly_chart(apply_theme(fig), use_container_width=True)
    st.caption("Bubble size = number of line items in the source file. Bottom-left = needs attention (low match rate AND low quality).")
else:
    st.info("No companies have field-mapping lineage recorded yet. Upload a new file to see this chart populate.")

if not no_lineage.empty:
    st.caption(f"{len(no_lineage)} compan{'y' if len(no_lineage) == 1 else 'ies'} uploaded before lineage tracking was added -- re-upload to include them here: "
               + ", ".join(no_lineage["company_name"].tolist()))

st.dataframe(
    health[["company_name", "source_filename", "quality_score", "total_issues",
            "high_severity", "fields_matched", "fields_total", "match_rate_pct"]],
    use_container_width=True, hide_index=True,
)

st.divider()

# ---------------------------------------------------------------------
# Drill into one company's mapping lineage
# ---------------------------------------------------------------------
st.subheader("2. Drill into one company's field mapping")

upload_id, company_name = render_upload_selector(conn)

summary = get_mapping_summary(conn, upload_id)

if summary["exact"] + summary["fuzzy_auto"] + summary["fuzzy_suggest"] + summary["unmatched"] == 0:
    st.info(
        "No mapping lineage recorded for this upload. This company was likely uploaded "
        "before lineage tracking was added -- re-upload it to capture this data."
    )
else:
    cols = st.columns(5)
    with cols[0]: powerbi_kpi("Exact Matches", str(summary["exact"]))
    with cols[1]: powerbi_kpi("Auto-Matched", str(summary["fuzzy_auto"]))
    with cols[2]: powerbi_kpi("Needs Review", str(summary["fuzzy_suggest"]))
    with cols[3]: powerbi_kpi("Unmatched", str(summary["unmatched"]))
    with cols[4]:
        conf = summary["avg_confidence"]
        powerbi_kpi("Avg Confidence", f"{conf:.0%}" if conf is not None else "N/A")

    if summary["unmatched"] > 0:
        status_badge(f"{summary['unmatched']} field(s) unmatched -- excluded from analysis", "warning")
    elif summary["fuzzy_suggest"] > 0:
        status_badge(f"{summary['fuzzy_suggest']} field(s) need manual review", "warning")
    else:
        status_badge("All fields matched with high confidence", "success")

    mapping_df = get_field_mapping(conn, upload_id)

    match_type_labels = {
        "exact": "Exact", "fuzzy_auto": "Auto-Matched (High Confidence)",
        "fuzzy_suggest": "Needs Review (Moderate Confidence)", "unmatched": "Unmatched",
    }
    mapping_df["match_type_label"] = mapping_df["match_type"].map(match_type_labels)

    st.markdown(f"#### Full field mapping for {company_name}")
    st.dataframe(
        mapping_df[["raw_label", "canonical_field", "confidence", "match_type_label"]]
        .rename(columns={"raw_label": "Source Label", "canonical_field": "Mapped To",
                          "confidence": "Confidence", "match_type_label": "Match Type"}),
        use_container_width=True, hide_index=True,
    )