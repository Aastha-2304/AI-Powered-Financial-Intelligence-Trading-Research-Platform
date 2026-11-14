"""
Professional PDF financial report generator:
- Built strictly using ReportLab.
- Formats executive summary, quality scores, historical statements table,
  DCF valuation metrics, scenario analysis, and academic research disclaimer.
- Zero independent arithmetic: tables pulled strictly from database records.
"""
from pathlib import Path
from typing import List, Dict, Any, Optional
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)

from app.core.constants import DISCLAIMER_TEXT
from app.schemas.financial import FinancialFact
from app.schemas.modeling import ValidationRun, ForecastRun, ValuationRun


class PDFReportExporter:
    """Generates institutional-grade PDF research reports."""

    @classmethod
    def generate_report(
        cls,
        output_path: Path,
        company_name: str,
        reporting_currency: str,
        dataset_id: str,
        dataset_version: int,
        historical_facts: List[FinancialFact],
        quality_run: Optional[ValidationRun] = None,
        forecast_run: Optional[ForecastRun] = None,
        valuation_run: Optional[ValuationRun] = None,
    ) -> Path:
        """Assembles PDF document using ReportLab."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=letter,
            rightMargin=54,
            leftMargin=54,
            topMargin=54,
            bottomMargin=54,
        )

        styles = getSampleStyleSheet()
        primary_color = colors.HexColor("#1A365D")
        accent_color = colors.HexColor("#2B6CB0")
        gray_text = colors.HexColor("#4A5568")

        title_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=24,
            textColor=primary_color,
            alignment=1,  # Center
        )
        subtitle_style = ParagraphStyle(
            "DocSubtitle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=11,
            leading=15,
            textColor=gray_text,
            alignment=1,
        )
        h1_style = ParagraphStyle(
            "Heading1_Custom",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=17,
            textColor=primary_color,
            spaceAfter=6,
        )
        body_style = ParagraphStyle(
            "Body_Custom",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            textColor=colors.HexColor("#2D3748"),
        )
        disclaimer_style = ParagraphStyle(
            "Disclaimer_Custom",
            parent=styles["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#718096"),
        )

        story = []

        # Title & Subtitle
        story.append(Paragraph("FINANCIAL INTELLIGENCE & VALUATION REPORT", title_style))
        story.append(Spacer(1, 4))
        story.append(Paragraph(f"Institutional Fundamental Research: {company_name}", subtitle_style))
        story.append(Spacer(1, 10))
        story.append(HRFlowable(width="100%", thickness=1.5, color=accent_color, spaceAfter=14))

        # Metadata Summary Box
        meta_data = [
            ["Company Entity:", company_name, "Reporting Currency:", f"{reporting_currency} (Base Scale)"],
            ["Dataset Version:", f"{dataset_id} (v{dataset_version})", "Classification:", "Research & Educational Analysis"],
        ]
        meta_table = Table(meta_data, colWidths=[110, 140, 110, 140])
        meta_table.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("TEXTCOLOR", (0, 0), (0, -1), primary_color),
            ("TEXTCOLOR", (2, 0), (2, -1), primary_color),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EDF2F7")),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 14))

        # Section 1: Executive Summary
        story.append(Paragraph("1. Executive Summary & Audit Lineage", h1_style))
        p_exec = (
            f"This audit and intrinsic valuation memorandum summarizes the reported financial statements "
            f"of {company_name}. Data ingestion was processed through normalized schema matching, verified "
            f"against accounting rules, and projected using multi-year driver schedules. "
            f"All presented figures correspond to committed database version {dataset_version}."
        )
        story.append(Paragraph(p_exec, body_style))
        story.append(Spacer(1, 12))

        # Section 2: Data Quality & Consistency
        story.append(Paragraph("2. Data Quality & Accounting Consistency", h1_style))
        if quality_run:
            q_rows = [
                ["Dimension", "Score", "Evaluation Metric"],
                ["Completeness", f"{quality_run.completeness_score:.1f}%", "Core mandatory line items verified"],
                ["Schema Mapping", f"{quality_run.mapping_quality_score:.1f}%", "Fuzzy & alias matching confidence"],
                ["Accounting Consistency", f"{quality_run.accounting_consistency_score:.1f}%", "Balance sheet & Cash flow identities"],
                ["Anomaly Severity", f"{quality_run.anomaly_severity_score:.1f}%", "Outlier movements across historical periods"],
                ["Overall Quality Score", f"{quality_run.overall_quality_score:.1f} / 100", "Weighted dimensional composite"],
            ]
            q_table = Table(q_rows, colWidths=[140, 90, 270])
            q_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), primary_color),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("ALIGN", (1, 0), (1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#E2E8F0")),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ]))
            story.append(q_table)
        story.append(Spacer(1, 14))

        # Section 3: Historical Financials Table
        story.append(Paragraph("3. Historical Financial Statements", h1_style))
        if historical_facts:
            periods = sorted(list({f.period for f in historical_facts}))[:4]
            items = sorted(list({f.canonical_item for f in historical_facts}))[:8]
            facts_map = {(f.canonical_item, f.period): f.normalized_value for f in historical_facts}

            hdr = ["Line Item (Canonical)"] + [str(p) for p in periods]
            table_rows = [hdr]
            for itm in items:
                row = [itm.replace("_", " ").title()]
                for p in periods:
                    val = facts_map.get((itm, p))
                    row.append(f"{val:,.2f}" if val is not None else "-")
                table_rows.append(row)

            col_w = 500 / len(hdr)
            hist_table = Table(table_rows, colWidths=[170] + [col_w] * (len(hdr) - 1))
            hist_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), accent_color),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
            ]))
            story.append(hist_table)
        story.append(Spacer(1, 14))

        # Section 4: Valuation Summary
        story.append(Paragraph("4. DCF Valuation & Scenario Summary", h1_style))
        if valuation_run:
            dcf_rows = [
                ["Valuation Component", "Calculated Output", "Methodology"],
                ["Discount Rate (WACC)", f"{valuation_run.wacc:.2%}", "CAPM Blended Cost of Capital"],
                ["Terminal Growth Rate (g)", f"{valuation_run.terminal_growth_rate:.2%}", "Gordon Constant Growth Model"],
                ["Enterprise Value (EV)", f"{valuation_run.enterprise_value:,.2f} {reporting_currency}", "Sum(PV of FCFs) + PV(Terminal Value)"],
                ["Equity Value", f"{valuation_run.equity_value:,.2f} {reporting_currency}", "Enterprise Value - Debt + Cash"],
                ["Implied Share Price", f"${valuation_run.implied_share_price:,.2f}" if valuation_run.implied_share_price else "N/A", "Equity Value / Diluted Shares"],
            ]
            dcf_table = Table(dcf_rows, colWidths=[150, 140, 210])
            dcf_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), primary_color),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
                ("ALIGN", (1, 1), (1, -1), "RIGHT"),
            ]))
            story.append(dcf_table)
        story.append(Spacer(1, 18))

        # Section 5: Academic Disclaimer
        story.append(Paragraph("5. Research & Academic Disclaimer", h1_style))
        story.append(Paragraph(DISCLAIMER_TEXT, disclaimer_style))

        doc.build(story)
        return output_path
