"""
Design system for AI Financial Intelligence Platform.
Power BI-inspired: deep charcoal canvas, one dominant accent color for data,
muted chrome, dense organized KPI tiles. Import and call load_custom_css()
at the top of every page, right after st.set_page_config().
"""
import streamlit as st

# ---------------------------------------------------------------------
# Palette reference (use these hex values in Plotly/chart_theme.py too,
# so charts and chrome stay visually consistent)
# ---------------------------------------------------------------------
BG_CANVAS = "#FDF2F8"       # page background -- soft pink
BG_SURFACE = "#FCE7F3"      # cards, sidebar -- slightly deeper pink
BG_SURFACE_2 = "#FBCFE8"    # hover / raised surface
ACCENT = "#8B5CF6"          # violet -- the ONE dominant data/interaction color
ACCENT_SOFT = "rgba(139, 92, 246, 0.12)"
POSITIVE = "#059669"
NEGATIVE = "#DC2626"
TEXT_PRIMARY = "#3B2A3D"
TEXT_MUTED = "#8B7089"
BORDER = "rgba(139, 92, 246, 0.15)"
SURFACE_ALT = "#DBEAFE"     # light blue -- dropdowns, tables, expanders


def load_custom_css():
    st.markdown(f"""
    <style>

    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap');

    html, body, [class*="css"] {{
        font-family: 'Inter', sans-serif;
        color: {TEXT_PRIMARY};
    }}
    h1, h2, h3, h4, h5, h6, p, span, label, li,
    .stMarkdown, [data-testid="stMarkdownContainer"] {{
        color: {TEXT_PRIMARY} !important;
    }}
    .stButton > button, .stButton > button * {{
        color: inherit;
    }}
    .stButton > button[kind="primary"], .stButton > button[kind="primary"] * {{
        color: #FFFFFF !important;
    }}
    [data-testid="stChatMessage"] p, [data-testid="stChatMessage"] span,
    [data-testid="stChatMessage"] div {{
        color: {TEXT_PRIMARY} !important;
    }}
    [data-testid="stMetricValue"], .stDataFrame, table {{
        font-family: 'JetBrains Mono', monospace;
    }}

    /* -----------------------------------------------------------
       Page canvas -- subtle radial vignette, not flat black
    ----------------------------------------------------------- */
    [data-testid="stAppViewContainer"] {{
        background:
            radial-gradient(circle at 15% 0%, rgba(139, 92, 246, 0.08), transparent 40%),
            radial-gradient(circle at 85% 100%, rgba(236, 72, 153, 0.06), transparent 40%),
            {BG_CANVAS};
    }}
    [data-testid="stHeader"] {{
        background: transparent;
    }}

    @keyframes fadeInUp {{
        from {{ opacity: 0; transform: translateY(10px); }}
        to   {{ opacity: 1; transform: translateY(0); }}
    }}
    .main .block-container {{
        animation: fadeInUp 0.4s ease-out;
        padding-top: 2rem;
    }}

    /* -----------------------------------------------------------
       File uploader -- native widget has its own dark chrome
    ----------------------------------------------------------- */
    [data-testid="stFileUploaderDropzone"] {{
        background: {BG_SURFACE} !important;
        border: 2px dashed {ACCENT} !important;
        border-radius: 10px;
    }}
    [data-testid="stFileUploaderDropzone"] * {{
        color: {TEXT_PRIMARY} !important;
    }}
    [data-testid="stFileUploaderDropzone"] button {{
        background: {ACCENT} !important;
        color: #FFFFFF !important;
        border: none !important;
    }}

    /* -----------------------------------------------------------
       Expanders -- default dark background
    ----------------------------------------------------------- */
    [data-testid="stExpander"] {{
        background: {SURFACE_ALT} !important;
        border: 1px solid {BORDER} !important;
        border-radius: 10px;
    }}
    [data-testid="stExpander"] summary {{
        color: {TEXT_PRIMARY} !important;
    }}

    /* -----------------------------------------------------------
       Select / multiselect dropdowns -- includes the popover menu,
       which Streamlit renders outside the normal DOM tree
    ----------------------------------------------------------- */
    [data-baseweb="select"] > div,
    [data-baseweb="popover"] {{
        background: {SURFACE_ALT} !important;
        color: {TEXT_PRIMARY} !important;
        border-color: {BORDER} !important;
    }}
    [data-baseweb="menu"] {{
        background: {SURFACE_ALT} !important;
    }}
    [data-baseweb="menu"] li {{
        color: {TEXT_PRIMARY} !important;
    }}
    [data-baseweb="menu"] li:hover {{
        background: {BG_SURFACE_2} !important;
    }}
    [data-baseweb="tag"] {{
        background: {ACCENT_SOFT} !important;
        color: {ACCENT} !important;
    }}

    /* -----------------------------------------------------------
       Number/text inputs -- dark chrome by default
    ----------------------------------------------------------- */
    [data-testid="stNumberInput"] input,
    [data-testid="stTextInput"] input,
    .stTextArea textarea {{
        background: {BG_SURFACE} !important;
        color: {TEXT_PRIMARY} !important;
        border-color: {BORDER} !important;
    }}

    /* -----------------------------------------------------------
       Plotly text safety net -- some SVG text elements ignore the
       figure-level font color config depending on trace type
    ----------------------------------------------------------- */
    .js-plotly-plot text {{
        fill: {TEXT_PRIMARY} !important;
    }}
    [data-testid="stSidebar"] {{
        background: {BG_SURFACE};
        border-right: 1px solid {BORDER};
    }}
    [data-testid="stSidebar"] * {{
        color: {TEXT_PRIMARY};
    }}
    [data-testid="stSidebarNav"] a {{
        border-radius: 8px;
        margin: 2px 8px;
        padding: 8px 12px !important;
        transition: background 0.15s ease, color 0.15s ease;
    }}
    [data-testid="stSidebarNav"] a:hover {{
        background: {BG_SURFACE_2};
    }}
    [data-testid="stSidebarNav"] a[aria-current="page"] {{
        background: {ACCENT_SOFT};
        border-left: 3px solid {ACCENT};
        font-weight: 600;
    }}
    [data-testid="stSidebarNav"] a[aria-current="page"] span {{
        color: {ACCENT} !important;
    }}

    /* -----------------------------------------------------------
       Gradient header -- solid accent bar, Power BI report-header feel
    ----------------------------------------------------------- */
    .gradient-header {{
        background: linear-gradient(135deg, {BG_SURFACE} 0%, {BG_SURFACE_2} 100%);
        border: 1px solid {BORDER};
        border-left: 4px solid {ACCENT};
        padding: 1.5rem 1.75rem;
        border-radius: 10px;
        margin-bottom: 1.5rem;
    }}
    .gradient-header h1 {{
        color: {TEXT_PRIMARY} !important;
        margin: 0;
        font-size: 1.6rem;
        font-weight: 700;
    }}
    .gradient-header p {{
        color: {TEXT_MUTED} !important;
        margin: 4px 0 0;
        font-size: 0.95rem;
    }}

    /* -----------------------------------------------------------
       Metric / KPI cards
    ----------------------------------------------------------- */
    [data-testid="stMetric"] {{
        background: {BG_SURFACE};
        border: 1px solid {BORDER};
        border-radius: 10px;
        padding: 1rem 1.2rem;
        transition: transform 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease;
    }}
    [data-testid="stMetric"]:hover {{
        transform: translateY(-3px);
        border-color: {ACCENT};
        box-shadow: 0 8px 20px rgba(139, 92, 246, 0.18);
    }}
    [data-testid="stMetricLabel"] {{
        color: {TEXT_MUTED} !important;
        font-size: 0.8rem !important;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }}

    /* -----------------------------------------------------------
       Buttons
    ----------------------------------------------------------- */
    .stButton > button {{
        border-radius: 8px;
        font-weight: 600;
        border: 1px solid {BORDER};
        transition: transform 0.15s ease, box-shadow 0.15s ease, border-color 0.15s ease;
    }}
    .stButton > button:hover {{
        transform: translateY(-2px);
        border-color: {ACCENT};
        box-shadow: 0 6px 16px rgba(139, 92, 246, 0.25);
    }}
    .stButton > button:active {{ transform: translateY(0) scale(0.98); }}
    .stButton > button[kind="primary"] {{
        background: {ACCENT};
        color: #FFFFFF;
        border: none;
    }}

    /* -----------------------------------------------------------
       Tables
    ----------------------------------------------------------- */
    .stDataFrame tbody tr:hover {{
        background-color: {ACCENT_SOFT} !important;
    }}
    [data-testid="stDataFrame"] {{
        background: {SURFACE_ALT} !important;
        border-radius: 10px;
        border: 1px solid {BORDER};
    }}

    /* -----------------------------------------------------------
       Tabs -- accent underline
    ----------------------------------------------------------- */
    .stTabs [aria-selected="true"] {{
        color: {ACCENT} !important;
        border-bottom-color: {ACCENT} !important;
    }}

    /* -----------------------------------------------------------
       Chat bubbles
    ----------------------------------------------------------- */
    @keyframes slideIn {{
        from {{ opacity: 0; transform: translateX(-8px); }}
        to   {{ opacity: 1; transform: translateX(0); }}
    }}
    [data-testid="stChatMessage"] {{
        animation: slideIn 0.22s ease-out;
        background: {BG_SURFACE};
        border: 1px solid {BORDER};
        border-radius: 10px;
    }}

    /* -----------------------------------------------------------
       Status badges
    ----------------------------------------------------------- */
    @keyframes pulse {{
        0%   {{ box-shadow: 0 0 0 0 rgba(5, 150, 105, 0.5); }}
        70%  {{ box-shadow: 0 0 0 8px rgba(5, 150, 105, 0); }}
        100% {{ box-shadow: 0 0 0 0 rgba(5, 150, 105, 0); }}
    }}
    .badge {{
        display: inline-flex; align-items: center; gap: 6px;
        padding: 4px 12px; border-radius: 999px;
        font-size: 0.8rem; font-weight: 600;
    }}
    .badge-dot {{ width: 8px; height: 8px; border-radius: 50%; }}
    .badge-success {{ background: rgba(61, 220, 151, 0.12); color: {POSITIVE}; }}
    .badge-success .badge-dot {{ background: {POSITIVE}; animation: pulse 2s infinite; }}
    .badge-warning {{ background: rgba(242, 201, 76, 0.12); color: {ACCENT}; }}
    .badge-warning .badge-dot {{ background: {ACCENT}; }}
    .badge-error {{ background: rgba(255, 107, 107, 0.12); color: {NEGATIVE}; }}
    .badge-error .badge-dot {{ background: {NEGATIVE}; }}

    /* -----------------------------------------------------------
       Power BI-style KPI tile (custom component, see powerbi_kpi())
    ----------------------------------------------------------- */
    .kpi-tile {{
        background: {BG_SURFACE};
        border: 1px solid {BORDER};
        border-radius: 10px;
        padding: 1.1rem 1.3rem;
        transition: transform 0.18s ease, border-color 0.18s ease;
    }}
    .kpi-tile:hover {{
        transform: translateY(-3px);
        border-color: {ACCENT};
    }}
    .kpi-label {{
        color: {TEXT_MUTED};
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        margin: 0 0 6px;
    }}
    .kpi-value {{
        font-family: 'JetBrains Mono', monospace;
        font-size: 1.9rem;
        font-weight: 700;
        color: {TEXT_PRIMARY};
        margin: 0;
    }}
    .kpi-delta {{
        font-size: 0.85rem;
        font-weight: 600;
        margin-top: 4px;
    }}
    .kpi-delta-up {{ color: {POSITIVE}; }}
    .kpi-delta-down {{ color: {NEGATIVE}; }}

    </style>
    """, unsafe_allow_html=True)


def gradient_header(title: str, subtitle: str = ""):
    """Report-header style banner -- replaces st.title()."""
    st.markdown(f"""
    <div class="gradient-header">
        <h1>{title}</h1>
        {f'<p>{subtitle}</p>' if subtitle else ''}
    </div>
    """, unsafe_allow_html=True)


def status_badge(label: str, status: str = "success"):
    """status: 'success' | 'warning' | 'error'."""
    st.markdown(f"""
    <span class="badge badge-{status}">
        <span class="badge-dot"></span>{label}
    </span>
    """, unsafe_allow_html=True)


def powerbi_kpi(label: str, value: str, delta: str = None, delta_positive: bool = True):
    """Renders one Power-BI-style KPI tile: muted label, large mono value,
    optional colored delta line. Use inside st.columns() for a KPI row:

        c1, c2, c3 = st.columns(3)
        with c1: powerbi_kpi("Revenue", "$4.2M", "+12.4%", delta_positive=True)
    """
    delta_html = ""
    if delta is not None:
        cls = "kpi-delta-up" if delta_positive else "kpi-delta-down"
        arrow = "▲" if delta_positive else "▼"
        delta_html = f'<div class="kpi-delta {cls}">{arrow} {delta}</div>'
    st.markdown(f"""
    <div class="kpi-tile">
        <p class="kpi-label">{label}</p>
        <p class="kpi-value">{value}</p>
        {delta_html}
    </div>
    """, unsafe_allow_html=True)