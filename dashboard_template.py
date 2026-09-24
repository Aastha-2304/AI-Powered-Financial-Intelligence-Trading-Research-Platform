"""
Power BI-style Financial Dashboard Template
Import this in your main Streamlit app
"""
import streamlit as st
from powerbi_styles import apply_powerbi_theme, create_powerbi_card, create_section_header, create_dashboard_grid

# Apply the Power BI theme
apply_powerbi_theme()

# ===========================
# Header
# ===========================
st.title("📊 Financial Analytics Dashboard")
st.caption("Real-time insights into your company's financial performance")

# ===========================
# Sidebar (filters & controls)
# ===========================
with st.sidebar:
    st.header("🎛️ Controls")

    # Example filters
    company = st.selectbox(
        "Select Company",
        ["Company A", "Company B", "Company C"]
    )

    year = st.selectbox(
        "Fiscal Year",
        [2024, 2023, 2022, 2021]
    )

    quarter = st.multiselect(
        "Quarter",
        ["Q1", "Q2", "Q3", "Q4"],
        default=["Q1", "Q2", "Q3", "Q4"]
    )

    st.divider()

    # Quick actions
    st.subheader("⚡ Quick Actions")
    if st.button("🔄 Refresh Data", use_container_width=True):
        st.rerun()

    if st.button("📥 Export Report", use_container_width=True):
        st.info("Report generation triggered!")

    if st.button("💬 Open Chatbot", use_container_width=True):
        st.info("Opening chatbot...")

# ===========================
# Top KPIs (Power BI-style tiles)
# ===========================
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

# ===========================
# Charts & Visualizations
# ===========================
create_section_header("Revenue & Profit Trends", "📊")

chart_row = create_dashboard_grid(2)

with chart_row[0]:
    st.subheader("Revenue Trend (Quarterly)")
    # Replace with your actual chart
    # import plotly.express as px
    # fig = px.line(df, x="quarter", y="revenue")
    # st.plotly_chart(fig, use_container_width=True)
    st.info("📈 Revenue chart placeholder - add your Plotly/Altair chart here")

with chart_row[1]:
    st.subheader("Profit Margin Analysis")
    # Replace with your actual chart
    st.info("📊 Margin chart placeholder - add your Plotly/Altair chart here")

st.divider()

# ===========================
# Financial Tables
# ===========================
create_section_header("Financial Statements", "📋")

table_tabs = st.tabs(["Income Statement", "Balance Sheet", "Cash Flow"])

with table_tabs[0]:
    st.subheader("Income Statement")
    # Replace with your actual dataframe
    # st.dataframe(income_df, use_container_width=True)
    st.info("📋 Income statement table placeholder - add your DataFrame here")

with table_tabs[1]:
    st.subheader("Balance Sheet")
    st.info("📋 Balance sheet table placeholder - add your DataFrame here")

with table_tabs[2]:
    st.subheader("Cash Flow Statement")
    st.info("📋 Cash flow table placeholder - add your DataFrame here")

st.divider()

# ===========================
# Chatbot Integration
# ===========================
create_section_header("AI Financial Analyst", "🤖")

st.caption("Ask questions about your financial data, run what-if scenarios, or get insights")

# Embed your existing chatbot here
# from chatbot_page import render_chatbot
# render_chatbot()

st.info("💬 Chatbot integration placeholder - embed your chatbot component here")

# ===========================
# Footer
# ===========================
st.divider()
st.caption("Data last updated: 2026-08-15 | Powered by Financial Analytics Platform")