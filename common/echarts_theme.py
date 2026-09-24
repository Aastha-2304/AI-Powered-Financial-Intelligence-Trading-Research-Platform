"""
ECharts theming for AI Financial Intelligence Platform.
Apache ECharts (via streamlit-echarts) gives smoother animations, richer
interactivity, and a more "modern BI tool" feel than Plotly's SVG
rendering. Same palette as chart_theme.py, different rendering engine.

Requires: pip install streamlit-echarts

Usage in any page:
    from echarts_theme import area_line_option, render
    option = area_line_option(
        categories=df["period"].tolist(),
        series={"Revenue": df["revenue"].tolist()},
        title="Revenue Trend",
    )
    render(option)
"""
from streamlit_echarts import st_echarts

PALETTE = ["#8B5CF6", "#059669", "#3B82F6", "#DC2626", "#EC4899", "#0D9488", "#D97706"]
POSITIVE = "#059669"
NEGATIVE = "#DC2626"
TEXT_COLOR = "#3B2A3D"
MUTED_COLOR = "#8B7089"
GRID_COLOR = "rgba(139, 92, 246, 0.12)"
FONT_FAMILY = "Inter, sans-serif"


def _axis_style():
    return {
        "axisLine": {"lineStyle": {"color": GRID_COLOR}},
        "axisLabel": {"color": TEXT_COLOR, "fontFamily": FONT_FAMILY},
        "splitLine": {"lineStyle": {"color": GRID_COLOR}},
    }


def area_line_option(categories: list, series: dict, title: str = "") -> dict:
    """series: {"Series Name": [values, ...]} -- pass multiple entries
    for a multi-line chart (e.g. one line per scenario)."""
    series_list = [
        {
            "name": name,
            "type": "line",
            "data": values,
            "smooth": True,
            "showSymbol": True,
            "symbolSize": 7,
            "lineStyle": {"width": 3},
            "areaStyle": {"opacity": 0.15},
            "animationDuration": 900,
            "animationEasing": "cubicOut",
        }
        for name, values in series.items()
    ]
    option = {
        "color": PALETTE,
        "tooltip": {"trigger": "axis"},
        "grid": {"left": "3%", "right": "4%", "bottom": "10%", "top": "18%", "containLabel": True},
        "xAxis": {"type": "category", "data": categories, **_axis_style()},
        "yAxis": {"type": "value", **_axis_style()},
        "series": series_list,
    }
    if title:
        option["title"] = {"text": title, "textStyle": {"color": TEXT_COLOR, "fontSize": 14, "fontFamily": FONT_FAMILY}}
    if len(series) > 1:
        option["legend"] = {"data": list(series.keys()), "textStyle": {"color": TEXT_COLOR}, "top": 0}
        option["grid"]["top"] = "22%"
    return option


def bar_option(categories: list, values: list, title: str = "", color_by_sign: bool = False) -> dict:
    if color_by_sign:
        data = [{"value": v, "itemStyle": {"color": POSITIVE if v >= 0 else NEGATIVE}} for v in values]
    else:
        data = values
    option = {
        "color": PALETTE,
        "tooltip": {"trigger": "axis"},
        "grid": {"left": "3%", "right": "4%", "bottom": "12%", "top": "18%", "containLabel": True},
        "xAxis": {"type": "category", "data": categories, "axisLabel": {"color": TEXT_COLOR, "rotate": 20, "fontFamily": FONT_FAMILY},
                  "axisLine": {"lineStyle": {"color": GRID_COLOR}}},
        "yAxis": {"type": "value", **_axis_style()},
        "series": [{
            "type": "bar", "data": data, "barMaxWidth": 42,
            "itemStyle": {"borderRadius": [6, 6, 0, 0], "color": None if color_by_sign else "#8B5CF6"},
            "animationDuration": 900, "animationEasing": "elasticOut",
        }],
    }
    if title:
        option["title"] = {"text": title, "textStyle": {"color": TEXT_COLOR, "fontSize": 14, "fontFamily": FONT_FAMILY}}
    return option


def gauge_option(value: float, title: str = "", min_val: float = 0, max_val: float = 100, suffix: str = "") -> dict:
    return {
        "series": [{
            "type": "gauge",
            "min": min_val, "max": max_val,
            "progress": {"show": True, "width": 14},
            "axisLine": {"lineStyle": {"width": 14, "color": [
                [0.4, NEGATIVE], [0.75, "#D97706"], [1, POSITIVE],
            ]}},
            "pointer": {"show": True, "itemStyle": {"color": "#8B5CF6"}},
            "axisTick": {"show": False},
            "splitLine": {"length": 10, "lineStyle": {"color": TEXT_COLOR}},
            "axisLabel": {"color": MUTED_COLOR, "fontSize": 10, "distance": 14},
            "title": {"show": True, "color": TEXT_COLOR, "fontSize": 13,
                      "fontFamily": FONT_FAMILY, "offsetCenter": [0, "72%"]},
            "detail": {
                "valueAnimation": True, "formatter": "{value}" + suffix,
                "color": TEXT_COLOR, "fontSize": 26, "fontFamily": FONT_FAMILY,
                "offsetCenter": [0, "38%"],
            },
            "data": [{"value": round(value, 1), "name": title}],
            "animationDuration": 1000,
        }],
    }


def donut_option(labels: list, values: list, title: str = "") -> dict:
    """Useful for the fuzzy-match breakdown (exact/auto/review/unmatched)
    or severity breakdown (high/medium/low) -- categorical proportions
    read better as a donut than a bar."""
    data = [{"name": label, "value": val} for label, val in zip(labels, values)]
    option = {
        "color": PALETTE,
        "tooltip": {"trigger": "item", "formatter": "{b}: {c} ({d}%)"},
        "legend": {"orient": "vertical", "left": "left", "textStyle": {"color": TEXT_COLOR}},
        "series": [{
            "type": "pie", "radius": ["45%", "70%"], "avoidLabelOverlap": True,
            "itemStyle": {"borderRadius": 8, "borderColor": "#FDF2F8", "borderWidth": 2},
            "label": {"color": TEXT_COLOR, "fontFamily": FONT_FAMILY},
            "data": data, "animationDuration": 900, "animationEasing": "cubicOut",
        }],
    }
    if title:
        option["title"] = {"text": title, "textStyle": {"color": TEXT_COLOR, "fontSize": 14, "fontFamily": FONT_FAMILY}}
    return option


def render(option: dict, height: str = "380px", key: str = None):
    """Renders any option dict built above."""
    st_echarts(options=option, height=height, key=key)