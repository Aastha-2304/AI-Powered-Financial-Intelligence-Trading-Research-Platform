"""
AI Financial Intelligence Platform - Main Dashboard
All pages use consistent Power BI-style theming from config.py
"""
import streamlit as st
from config import init_app, create_powerbi_card, create_section_header, create_dashboard_grid

# IMPORTANT: Initialize app FIRST (before any other st.* commands)
init_app(page_title="Financial Analytics Platform", page_icon="📊", layout="wide")

# ===========================
# Navigation (Sidebar)
# ===========================
with st.sidebar:
    st.markdown("### 🧭 Navigation")

    page = st.radio(
        "Go to",
        [
            "📊 Dashboard",
            "📈 Analytics",
            "💬 Chatbot",
            "📋 Reports",
            "⚙️ Settings"
        ],
        label_visibility="collapsed"
    )

    st.divider()

    # Data filters
    st.markdown("### 🎛️ Filters")
    company = st.selectbox(
        "Company",
        ["Company A", "Company B", "Company C"],
        key="sidebar_company"
    )

    year = st.selectbox(
        "Fiscal Year",
        [2024, 2023, 2022, 2021],
        key="sidebar_year"
    )

    st.divider()

    # Quick actions
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.rerun()

    if st.button("📥 Export Report", use_container_width=True):
        st.success("Report exported successfully!")

# ===========================
# Main Content Area
# ===========================

# Page routing
if page == "📊 Dashboard":
    # Header
    st.title("📊 Financial Analytics Dashboard")
    st.caption(f"Real-time insights for {company} | FY {year}")

    st.divider()

    # Top KPIs
    create_section_header("Key Performance Indicators", "📈")

    kpi_cols = create_dashboard_grid(4)

    with kpi_cols[0]:
        create_powerbi_card(
            title="Total Revenue",
            value="$12.5M",
            delta="+8.2%",
            delta_label="vs last quarter"
        )

    with kpi_cols[1]:
        create_powerbi_card(
            title="Net Income",
            value="$2.8M",
            delta="+12.5%",
            delta_label="vs last quarter"
        )

    with kpi_cols[2]:
        create_powerbi_card(
            title="EBITDA Margin",
            value="24.3%",
            delta="+1.8%",
            delta_label="vs last quarter"
        )

    with kpi_cols[3]:
        create_powerbi_card(
            title="Free Cash Flow",
            value="$1.9M",
            delta="-3.2%",
            delta_label="vs last quarter"
        )

    st.divider()

    # Charts
    create_section_header("Revenue & Profit Trends", "📊")

    chart_row = create_dashboard_grid(2)

    with chart_row[0]:
        st.subheader("Revenue Trend (Quarterly)")
        st.info("📈 Revenue chart - add your Plotly/Altair chart here")

    with chart_row[1]:
        st.subheader("Profit Margin Analysis")
        st.info("📊 Margin chart - add your Plotly/Altair chart here")

    st.divider()

    # Financial Tables
    create_section_header("Financial Statements", "📋")

    table_tabs = st.tabs(["Income Statement", "Balance Sheet", "Cash Flow"])

    with table_tabs[0]:
        st.subheader("Income Statement")
        st.info("📋 Income statement table - add your DataFrame here")

    with table_tabs[1]:
        st.subheader("Balance Sheet")
        st.info("📋 Balance sheet table - add your DataFrame here")

    with table_tabs[2]:
        st.subheader("Cash Flow Statement")
        st.info("📋 Cash flow table - add your DataFrame here")

elif page == "📈 Analytics":
    st.title("📈 Advanced Analytics")
    st.caption("Deep-dive analysis, ratios, forecasting, and valuation")

    st.divider()

    create_section_header("Financial Ratios", "📊")

    ratio_cols = create_dashboard_grid(3)

    with ratio_cols[0]:
        create_powerbi_card(
            title="Current Ratio",
            value="2.4",
            delta="+0.3",
            delta_label="vs last year"
        )

    with ratio_cols[1]:
        create_powerbi_card(
            title="Debt-to-Equity",
            value="0.45",
            delta="-0.08",
            delta_label="vs last year"
        )

    with ratio_cols[2]:
        create_powerbi_card(
            title="ROE",
            value="18.5%",
            delta="+2.1%",
            delta_label="vs last year"
        )

    st.divider()

    create_section_header("Forecasting & Valuation", "🔮")
    st.info("🔮 DCF valuation and forecasting models - integrate your models here")

elif page == "💬 Chatbot":
    st.title("💬 AI Financial Analyst")
    st.caption("Ask questions about your financial data, run what-if scenarios")

    st.divider()

    # Embed your enhanced chatbot here
    st.info("💬 Chatbot integration - import chatbot_enhanced.py or your chatbot module here")

    # Example:
    # from chatbot_enhanced import render_chatbot
    # render_chatbot()

elif page == "📋 Reports":
    st.title("📋 Report Generation")
    st.caption("Generate professional DOCX and PDF reports")

    st.divider()

    create_section_header("Generate Report", "📄")

    report_type = st.radio(
        "Report Type",
        ["Executive Summary", "Full Financial Report", "Valuation Report", "Custom Report"]
    )

    format = st.radio(
        "Export Format",
        ["DOCX", "PDF", "Both"]
    )

    if st.button("📥 Generate Report", type="primary"):
        st.success(f"Generating {report_type} in {format} format...")
        st.info("📄 Integrate your docx/PDF generation logic here")

elif page == "⚙️ Settings":
    st.title("⚙️ Platform Settings")
    st.caption("Configure your workspace and preferences")

    st.divider()

    create_section_header("Data Sources", "🗄️")
    st.info("🗄️ Configure data connections and ETL pipelines")

    create_section_header("API Keys", "🔑")
    st.info("🔑 Manage API keys (Groq, data providers, etc.)")

    create_section_header("Theme", "🎨")
    st.info("🎨 Customize colors, logo, and branding")

# ===========================
# Footer
# ===========================
st.divider()
st.caption(
    "Data last updated: 2026-08-15 21:45 IST | "
    "Powered by AI Financial Intelligence Platform"
)