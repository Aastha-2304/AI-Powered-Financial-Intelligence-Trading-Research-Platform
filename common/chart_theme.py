"""
Chart theming for AI Financial Intelligence Platform.
A reusable Plotly theme + chart helpers so every chart in the app shares
the same vivid, interactive, "product-like" visual language instead of
default Plotly gray-on-white.

Usage in any page:
    from chart_theme import apply_theme, kpi_gauge, area_line_chart
    fig = px.line(df, x="period", y="revenue")
    st.plotly_chart(apply_theme(fig), use_container_width=True)
"""
import plotly.express as px
import plotly.graph_objects as go

PALETTE = ["#8B5CF6", "#059669", "#3B82F6", "#DC2626", "#EC4899", "#0D9488", "#D97706"]

POSITIVE = "#059669"
NEGATIVE = "#DC2626"
NEUTRAL = "#8B5CF6"

FONT_FAMILY = "Inter, sans-serif"


def apply_theme(fig: go.Figure, height: int = 380) -> go.Figure:
    """Applies the shared dark, colorful, animated look to any Plotly figure.
    Call this right before st.plotly_chart() on every chart in the app."""
    fig.update_layout(
        template="plotly_white",
        colorway=PALETTE,
        font=dict(family=FONT_FAMILY, size=13, color="#3B2A3D"),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=height,
        margin=dict(l=10, r=10, t=40, b=10),
        hoverlabel=dict(
            bgcolor="#FFFFFF",
            font_size=13,
            font_family=FONT_FAMILY,
            bordercolor="rgba(139, 92, 246, 0.3)",
        ),
        hovermode="x unified",
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
            bgcolor="rgba(0,0,0,0)",
        ),
        transition=dict(duration=400, easing="cubic-in-out"),
        xaxis=dict(gridcolor="rgba(139, 92, 246, 0.10)", zeroline=False),
        yaxis=dict(gridcolor="rgba(139, 92, 246, 0.10)", zeroline=False),
    )
    return fig


def area_line_chart(df, x: str, y, title: str = "", colors=None):
    """Line chart with a soft gradient fill under the line -- reads as
    much more 'alive' than a bare line. `y` can be a single column name
    or a list of columns for multi-series."""
    fig = px.line(df, x=x, y=y, markers=True, title=title,
                   color_discrete_sequence=colors or PALETTE)
    fig.update_traces(fill="tozeroy", line=dict(width=3), marker=dict(size=6))
    return apply_theme(fig)


def colored_bar_chart(df, x: str, y: str, title: str = "", color_by_sign: bool = False):
    """Bar chart. If color_by_sign=True, positive values render green and
    negative render red -- useful for variance/leakage-style charts."""
    if color_by_sign:
        colors = [POSITIVE if v >= 0 else NEGATIVE for v in df[y]]
        fig = go.Figure(go.Bar(x=df[x], y=df[y], marker_color=colors))
        fig.update_layout(title=title)
    else:
        fig = px.bar(df, x=x, y=y, title=title, color_discrete_sequence=PALETTE)
    return apply_theme(fig)


def kpi_gauge(value: float, title: str, min_val: float = 0, max_val: float = 100,
              suffix: str = "", delta_reference: float = None) -> go.Figure:
    """A colorful animated gauge for a single headline KPI -- e.g. Data
    Quality Score, or a ratio against a healthy-range band. This is the
    single highest 'wow factor per line of code' chart type available."""
    steps = [
        {"range": [min_val, min_val + (max_val - min_val) * 0.4], "color": "rgba(239,68,68,0.25)"},
        {"range": [min_val + (max_val - min_val) * 0.4, min_val + (max_val - min_val) * 0.75], "color": "rgba(234,179,8,0.25)"},
        {"range": [min_val + (max_val - min_val) * 0.75, max_val], "color": "rgba(34,197,94,0.25)"},
    ]

    indicator_kwargs = dict(
        mode="gauge+number" + ("+delta" if delta_reference is not None else ""),
        value=value,
        number={"suffix": suffix, "font": {"size": 36}},
        title={"text": title, "font": {"size": 15}},
        gauge={
            "axis": {"range": [min_val, max_val], "tickcolor": "#E5E7EB"},
            "bar": {"color": NEUTRAL},
            "steps": steps,
            "threshold": {
                "line": {"color": "white", "width": 3},
                "thickness": 0.85,
                "value": value,
            },
        },
    )
    if delta_reference is not None:
        indicator_kwargs["delta"] = {"reference": delta_reference}

    fig = go.Figure(go.Indicator(**indicator_kwargs))
    return apply_theme(fig, height=280)


def sparkline(df, x: str, y: str, color: str = NEUTRAL):
    """Minimal, axis-free trend line -- good for small inline trend
    indicators next to a metric card rather than a full chart."""
    fig = go.Figure(go.Scatter(x=df[x], y=df[y], mode="lines", line=dict(color=color, width=2), fill="tozeroy"))
    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        height=80,
        margin=dict(l=0, r=0, t=0, b=0),
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        showlegend=False,
    )
    return fig