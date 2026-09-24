"""
Report Generator module for AI Financial Intelligence Platform
Gathers a company's full analysis (historical data, ratios, validation,
forecast, DCF valuation) into a single structured object, then renders
it to Word (.docx) and PDF.
"""
import sys
from pathlib import Path
from datetime import datetime
import duckdb
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

sys.path.append(str(Path(__file__).resolve().parent.parent))
from config import DB_PATH

sys.path.append(str(Path(__file__).resolve().parent.parent / "forecasting"))
sys.path.append(str(Path(__file__).resolve().parent.parent / "financial_model"))
from revenue_forecast import get_historical_data, derive_default_assumptions, project_income_statement, get_latest_period_value
from balance_sheet import derive_working_capital_assumptions, project_working_capital, finalize_balance_sheet, get_balancing_items
from cash_flow import project_cash_flow
from dcf import compute_free_cash_flow, run_dcf, estimate_net_debt
from chatbot import generate_narrative_commentary


def gather_report_data(conn, upload_id: str, discount_rate: float = 0.10,
                        terminal_growth: float = 0.025, years_forward: int = 5) -> dict:
    """Collects everything needed for a full report into one dict."""
    company_row = conn.execute(
        "SELECT company_name, source_filename, uploaded_at FROM uploads WHERE upload_id = ?", [upload_id]
    ).fetchone()
    company_name, source_filename, uploaded_at = company_row

    hist_df = get_historical_data(conn, upload_id)

    score_row = conn.execute("""
        SELECT score, total_issues, high_severity, medium_severity, low_severity
        FROM quality_scores WHERE upload_id = ?
    """, [upload_id]).fetchdf()
    quality_score = score_row.iloc[0].to_dict() if not score_row.empty else {}

    issues = conn.execute("""
        SELECT check_name, line_item, period, severity, message
        FROM validation_issues WHERE upload_id = ?
    """, [upload_id]).fetchdf()

    ratios = conn.execute("""
        SELECT category, ratio_name, period, value FROM financial_ratios WHERE upload_id = ?
    """, [upload_id]).fetchdf()

    income_assumptions = derive_default_assumptions(hist_df)
    income_projection = project_income_statement(hist_df, income_assumptions, years_forward=years_forward)

    wc_assumptions = derive_working_capital_assumptions(hist_df)
    starting_total_assets = get_latest_period_value(hist_df, "total_assets") or 0.0
    starting_current_assets = get_latest_period_value(hist_df, "total_current_assets") or 0.0
    starting_non_current_assets = starting_total_assets - starting_current_assets
    balancing_items = get_balancing_items(hist_df)

    working_capital = project_working_capital(
        income_projection, hist_df, wc_assumptions, starting_non_current_assets, balancing_items
    )

    starting_cash = get_latest_period_value(hist_df, "cash_and_equivalents") or 0.0
    starting_ar = get_latest_period_value(hist_df, "accounts_receivable") or 0.0
    starting_inventory = get_latest_period_value(hist_df, "inventory") or 0.0
    starting_ap = get_latest_period_value(hist_df, "accounts_payable") or 0.0
    starting_current_liab = get_latest_period_value(hist_df, "total_current_liabilities") or 0.0
    starting_other_liab = starting_current_liab - starting_ap

    cash_flow = project_cash_flow(
        income_projection, working_capital, starting_cash,
        starting_ar=starting_ar, starting_inventory=starting_inventory,
        starting_ap=starting_ap, starting_other_liab=starting_other_liab,
    )

    complete_balance_sheet = finalize_balance_sheet(working_capital, cash_flow)

    fcf_df = compute_free_cash_flow(cash_flow)
    net_debt = estimate_net_debt(hist_df)
    dcf_result = run_dcf(fcf_df, discount_rate, terminal_growth, net_debt)

    return {
        "company_name": company_name,
        "source_filename": source_filename,
        "uploaded_at": uploaded_at,
        "generated_at": datetime.now(),
        "historical_data": hist_df,
        "quality_score": quality_score,
        "validation_issues": issues,
        "ratios": ratios,
        "income_assumptions": income_assumptions,
        "income_projection": income_projection,
        "complete_balance_sheet": complete_balance_sheet,
        "cash_flow": cash_flow,
        "dcf_result": dcf_result,
        "discount_rate": discount_rate,
        "terminal_growth": terminal_growth,
    }


def render_docx_report(data: dict, output_path: str):
    from docx import Document
    from docx.shared import Pt

    doc = Document()
    doc.add_heading("Financial Analysis Report", level=0)
    doc.add_paragraph(f"Company: {data['company_name']}")
    doc.add_paragraph(f"Source file: {data['source_filename']}")
    doc.add_paragraph(f"Generated: {data['generated_at'].strftime('%Y-%m-%d %H:%M')}")
    doc.add_paragraph("")

    doc.add_heading("Management Commentary", level=1)
    try:
        commentary = generate_narrative_commentary(data)
        doc.add_paragraph(commentary)
    except Exception as e:
        doc.add_paragraph(
            "AI-generated commentary is unavailable for this report "
            f"(reason: {e}). All figures below are still complete and accurate."
        )
    doc.add_paragraph("")

    doc.add_heading("Data Quality", level=1)
    q = data["quality_score"]
    if q:
        doc.add_paragraph(f"Quality Score: {int(q.get('score', 0))}/100")
        doc.add_paragraph(
            f"Total Issues: {int(q.get('total_issues', 0))} "
            f"(High: {int(q.get('high_severity', 0))}, "
            f"Medium: {int(q.get('medium_severity', 0))}, "
            f"Low: {int(q.get('low_severity', 0))})"
        )
    issues = data["validation_issues"]
    if not issues.empty:
        doc.add_paragraph("Issues found:")
        table = doc.add_table(rows=1, cols=4)
        table.style = "Light Grid Accent 1"
        hdr = table.rows[0].cells
        hdr[0].text, hdr[1].text, hdr[2].text, hdr[3].text = "Severity", "Line Item", "Period", "Message"
        for _, row in issues.iterrows():
            cells = table.add_row().cells
            cells[0].text = str(row["severity"])
            cells[1].text = str(row["line_item"])
            cells[2].text = str(row["period"])
            cells[3].text = str(row["message"])

    doc.add_heading("Historical Financial Summary", level=1)
    hist_df = data["historical_data"]
    key_items = ["revenue", "net_income", "total_assets", "total_liabilities", "total_equity"]
    periods = sorted([c for c in hist_df.columns if c != "line_item"])
    table = doc.add_table(rows=1, cols=len(periods) + 1)
    table.style = "Light Grid Accent 1"
    hdr = table.rows[0].cells
    hdr[0].text = "Line Item"
    for i, p in enumerate(periods):
        hdr[i + 1].text = p
    for item in key_items:
        row_data = hist_df[hist_df["line_item"] == item]
        if row_data.empty:
            continue
        cells = table.add_row().cells
        cells[0].text = item.replace("_", " ").title()
        for i, p in enumerate(periods):
            val = row_data[p].iloc[0] if p in row_data.columns else None
            cells[i + 1].text = f"{val:,.0f}" if val is not None else "-"

    doc.add_heading("Financial Ratios", level=1)
    ratios = data["ratios"]
    if not ratios.empty:
        latest_period = sorted(ratios["period"].unique())[-1]
        latest = ratios[ratios["period"] == latest_period]
        table = doc.add_table(rows=1, cols=3)
        table.style = "Light Grid Accent 1"
        hdr = table.rows[0].cells
        hdr[0].text, hdr[1].text, hdr[2].text = "Category", "Ratio", "Value"
        for _, row in latest.iterrows():
            cells = table.add_row().cells
            cells[0].text = str(row["category"]).title()
            cells[1].text = str(row["ratio_name"]).replace("_", " ").title()
            cells[2].text = f"{row['value']:,.2f}"

    doc.add_heading("Financial Forecast", level=1)
    doc.add_paragraph("Key assumptions (auto-derived from historical trend):")
    for k, v in data["income_assumptions"].items():
        doc.add_paragraph(f"  - {k.replace('_', ' ').title()}: {v*100:.2f}%", style="List Bullet")

    proj = data["income_projection"]
    table = doc.add_table(rows=1, cols=len(proj.columns))
    table.style = "Light Grid Accent 1"
    hdr = table.rows[0].cells
    for i, col in enumerate(proj.columns):
        hdr[i].text = col.replace("_", " ").title()
    for _, row in proj.iterrows():
        cells = table.add_row().cells
        for i, col in enumerate(proj.columns):
            val = row[col]
            cells[i].text = f"{val:,.0f}" if isinstance(val, (int, float)) else str(val)

    doc.add_heading("DCF Valuation", level=1)
    dcf = data["dcf_result"]
    doc.add_paragraph(f"Discount Rate: {data['discount_rate']*100:.1f}%")
    doc.add_paragraph(f"Terminal Growth Rate: {data['terminal_growth']*100:.1f}%")
    doc.add_paragraph(f"Sum of Discounted FCFs: ${dcf['sum_discounted_fcf']:,.2f}")
    doc.add_paragraph(f"Discounted Terminal Value: ${dcf['discounted_terminal_value']:,.2f}")
    doc.add_paragraph(f"Enterprise Value: ${dcf['enterprise_value']:,.2f}")
    doc.add_paragraph(f"Net Debt: ${dcf['net_debt']:,.2f}")
    p = doc.add_paragraph()
    run = p.add_run(f"Implied Equity Value: ${dcf['equity_value']:,.2f}")
    run.bold = True
    run.font.size = Pt(14)

    doc.save(output_path)
    return output_path