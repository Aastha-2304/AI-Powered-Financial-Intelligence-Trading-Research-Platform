"""
Shared UI widgets, styling helpers, and Power BI / Trading Terminal aesthetics.
"""
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

CUSTOM_CSS = """
<style>
/* Institutional Trading Terminal Styling */
.main {
    background-color: #0E131F;
    color: #F8FAFC;
    font-family: 'Inter', -apple-system, sans-serif;
}
.stMetric {
    background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 12px 16px;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
}
.stMetric label {
    color: #94A3B8 !important;
    font-size: 0.85rem !important;
    font-weight: 500 !important;
}
.stMetric div[data-testid="stMetricValue"] {
    color: #F8FAFC !important;
    font-size: 1.5rem !important;
    font-weight: 700 !important;
}
.kpi-card {
    background: #1E293B;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 12px;
}
.provenance-tag {
    display: inline-block;
    padding: 2px 8px;
    font-size: 11px;
    font-family: monospace;
    color: #38BDF8;
    background: rgba(56, 189, 248, 0.1);
    border: 1px solid rgba(56, 189, 248, 0.3);
    border-radius: 4px;
    margin-top: 4px;
}
.disclaimer-banner {
    padding: 10px 14px;
    background: rgba(30, 41, 59, 0.8);
    border-left: 4px solid #38BDF8;
    border-radius: 4px;
    font-size: 12px;
    color: #94A3B8;
    margin-top: 24px;
}
</style>
"""


def load_terminal_theme():
    """Injects institutional styling."""
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def render_disclaimer():
    """Renders mandatory academic research disclaimer."""
    from app.core.constants import DISCLAIMER_TEXT
    st.markdown(
        f'<div class="disclaimer-banner"><b>Academic Disclaimer:</b> {DISCLAIMER_TEXT}</div>',
        unsafe_allow_html=True,
    )


def render_provenance_badge(source_file: str, row: int, period: str, version: int):
    """Renders provenance citation badge."""
    st.markdown(
        f'<span class="provenance-tag">Source: {source_file} (row {row}) | {period} | v{version}</span>',
        unsafe_allow_html=True,
    )
