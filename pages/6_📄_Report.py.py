"""
Report -- generate the full financial analysis report (docx + PDF) for a company
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent))
sys.path.append(str(Path(__file__).resolve().parent.parent / "common"))
sys.path.append(str(Path(__file__).resolve().parent.parent / "ai_agent"))

import streamlit as st

from shared_utils import get_connection, render_upload_selector
from config import PROJECT_ROOT
from styles import load_custom_css, gradient_header, status_badge
from report_generator import gather_report_data, render_docx_report

st.set_page_config(page_title="Report", layout="wide")
load_custom_css()
gradient_header("Financial Analysis Report", "Generate a full Word/PDF report -- data quality, ratios, forecast, and DCF valuation")

conn = get_connection()
upload_id, company_name = render_upload_selector(conn)

REPORTS_DIR = PROJECT_ROOT / "data" / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

st.divider()

col1, col2 = st.columns(2)
discount_rate = col1.number_input("Discount rate (%)", min_value=1.0, max_value=30.0, value=10.0, step=0.5) / 100
terminal_growth = col2.number_input("Terminal growth rate (%)", min_value=0.0, max_value=10.0, value=2.5, step=0.25) / 100

if st.button("Generate Report", type="primary"):
    safe_name = "".join(c if c.isalnum() else "_" for c in company_name)
    docx_path = REPORTS_DIR / f"{safe_name}_report.docx"
    pdf_path = REPORTS_DIR / f"{safe_name}_report.pdf"

    with st.spinner("Gathering data and building the report..."):
        data = gather_report_data(conn, upload_id, discount_rate=discount_rate, terminal_growth=terminal_growth)
        render_docx_report(data, str(docx_path))

    status_badge("Word report generated", "success")
    st.success(f"Word report generated: {docx_path.name}")

    pdf_ready = False
    with st.spinner("Converting to PDF..."):
        try:
            from docx2pdf import convert
            convert(str(docx_path), str(pdf_path))
            pdf_ready = pdf_path.exists()
        except Exception as e:
            status_badge("PDF conversion failed", "error")
            st.warning(
                f"PDF conversion failed ({e}). The Word file is still available below. "
                "Make sure Microsoft Word is installed and not blocked by another open instance, then try again."
            )

    dl_col1, dl_col2 = st.columns(2)
    with open(docx_path, "rb") as f:
        dl_col1.download_button(
            "Download Word (.docx)", f, file_name=docx_path.name,
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    if pdf_ready:
        with open(pdf_path, "rb") as f:
            dl_col2.download_button(
                "Download PDF", f, file_name=pdf_path.name, mime="application/pdf",
            )

st.divider()
st.caption(f"Generated reports are saved locally to: {REPORTS_DIR}")