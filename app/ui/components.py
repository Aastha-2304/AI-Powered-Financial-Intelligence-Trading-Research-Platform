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
    """Hidden from frontend per user request."""
    pass


def render_provenance_badge(source_file: str, row: int, period: str, version: int):
    """Renders provenance citation badge."""
    st.markdown(
        f'<span class="provenance-tag">Source: {source_file} (row {row}) | {period} | v{version}</span>',
        unsafe_allow_html=True,
    )


def render_sidebar_company_selector(conn):
    """
    Standardizes sidebar company selection across all application pages.
    Returns (active_company_id, active_company_name).
    If no company has been uploaded/registered yet, returns (None, None).
    """
    from app.database.repositories import CompanyRepository
    from app.schemas.financial import Company

    comp_repo = CompanyRepository(conn)
    companies = comp_repo.list_all()

    with st.sidebar:
        st.title("🏦 Financial Platform")
        st.caption("Active Entity Scope")

        if not companies:
            st.info("No entity uploaded yet. Upload statements on Home screen to begin.")
            selected_company_id = None
            selected_name = None
            st.session_state["active_company_id"] = None
            st.session_state["active_company_name"] = None
        else:
            company_options = {c.name: c.company_id for c in companies}
            names_list = list(company_options.keys())

            # Pre-select from session state if available
            current_active_id = st.session_state.get("active_company_id")
            default_idx = 0
            if current_active_id:
                for i, name in enumerate(names_list):
                    if company_options[name] == current_active_id:
                        default_idx = i
                        break

            selected_name = st.selectbox("Company", names_list, index=default_idx, key="sidebar_company_select")
            selected_company_id = company_options[selected_name]

            st.session_state["active_company_id"] = selected_company_id
            st.session_state["active_company_name"] = selected_name

        # Option to create/register a new company
        with st.expander("➕ Register New Entity"):
            with st.form("new_company_form", clear_on_submit=True):
                new_name = st.text_input("Company Name", placeholder="e.g. Microsoft Corp")
                new_ticker = st.text_input("Ticker", placeholder="e.g. MSFT")
                new_currency = st.selectbox("Currency", ["USD", "INR", "EUR", "GBP"])
                if st.form_submit_button("Create Entity"):
                    if new_name:
                        new_id = f"co_{new_name.lower().replace(' ', '_')[:12]}"
                        comp_repo.create(
                            Company(
                                company_id=new_id,
                                name=new_name,
                                ticker=new_ticker.upper() if new_ticker else None,
                                reporting_currency=new_currency,
                            )
                        )
                        st.session_state["active_company_id"] = new_id
                        st.session_state["active_company_name"] = new_name
                        st.success(f"Created {new_name}!")
                        st.rerun()

        st.divider()

    return selected_company_id, selected_name
