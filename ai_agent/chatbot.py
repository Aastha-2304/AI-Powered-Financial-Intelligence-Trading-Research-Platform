"""
Chatbot module for AI Financial Intelligence Platform
--------------------------------------------------------------
Three capabilities in one module:

1. Q&A over a company's uploaded financials (grounded in DuckDB, not a
   vector store -- the data is small and structured, so we retrieve exact
   rows instead of doing embedding search).
2. Narrative commentary generation for the Word/PDF report (MD&A-style
   paragraph written from the already-computed numbers).
3. Agentic re-forecasting / what-if scenarios -- the model can call real
   Python functions (via Claude tool use) that re-run the existing
   forecast, working-capital, cash-flow, and DCF modules with overridden
   assumptions, and report back the new numbers in the conversation.

Design note: this module never invents financial figures itself. Every
number the model states either comes straight from a DB query result or
from a tool call into revenue_forecast.py / balance_sheet.py /
cash_flow.py / dcf.py -- the exact same functions report_generator.py
uses. This keeps the chatbot's answers consistent with the generated
report.
"""
import os
import sys
import json
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent))
sys.path.append(str(Path(__file__).resolve().parent / "forecasting"))
sys.path.append(str(Path(__file__).resolve().parent / "financial_model"))

from revenue_forecast import (
    get_historical_data,
    derive_default_assumptions,
    project_income_statement,
    get_latest_period_value,
)
from balance_sheet import (
    derive_working_capital_assumptions,
    project_working_capital,
    finalize_balance_sheet,
    get_balancing_items,
)
from cash_flow import project_cash_flow
from dcf import compute_free_cash_flow, run_dcf, estimate_net_debt

try:
    from groq import Groq
except ImportError:
    Groq = None

GROQ_MODEL = "llama-3.3-70b-versatile"
MAX_TOOL_ITERATIONS = 6


# ---------------------------------------------------------------------
# Context building -- pulls exact figures out of DuckDB, no guessing
# ---------------------------------------------------------------------

def _get_client():
    if Groq is None:
        raise RuntimeError(
            "The 'groq' package is not installed. Run: pip install groq"
        )
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY environment variable is not set.")
    return Groq(api_key=api_key)


def build_company_snapshot(conn, upload_id: str) -> dict:
    """Pulls everything needed to ground the chatbot for one company:
    identity, latest quality score, open validation issues, and the
    most recent period's ratios. Kept small on purpose -- this goes
    straight into the system prompt on every turn."""
    company_row = conn.execute(
        "SELECT company_name, source_filename, uploaded_at FROM uploads WHERE upload_id = ?",
        [upload_id],
    ).fetchone()
    if company_row is None:
        raise ValueError(f"No upload found for upload_id={upload_id}")
    company_name, source_filename, uploaded_at = company_row

    score_row = conn.execute(
        """
        SELECT score, total_issues, high_severity, medium_severity, low_severity
        FROM quality_scores WHERE upload_id = ?
        """,
        [upload_id],
    ).fetchdf()
    quality_score = score_row.iloc[0].to_dict() if not score_row.empty else {}

    ratios = conn.execute(
        "SELECT category, ratio_name, period, value FROM financial_ratios WHERE upload_id = ?",
        [upload_id],
    ).fetchdf()
    latest_ratios = pd.DataFrame()
    if not ratios.empty:
        latest_period = sorted(ratios["period"].unique())[-1]
        latest_ratios = ratios[ratios["period"] == latest_period]

    hist_df = get_historical_data(conn, upload_id)

    return {
        "company_name": company_name,
        "source_filename": source_filename,
        "uploaded_at": str(uploaded_at),
        "quality_score": quality_score,
        "latest_ratios": latest_ratios,
        "historical_data": hist_df,
    }


def _snapshot_to_prompt_text(snapshot: dict) -> str:
    lines = [
        f"Company: {snapshot['company_name']}",
        f"Source file: {snapshot['source_filename']}",
        f"Uploaded: {snapshot['uploaded_at']}",
    ]
    q = snapshot["quality_score"]
    if q:
        lines.append(
            f"Data quality score: {int(q.get('score', 0))}/100 "
            f"({int(q.get('total_issues', 0))} issues: "
            f"{int(q.get('high_severity', 0))} high, "
            f"{int(q.get('medium_severity', 0))} medium, "
            f"{int(q.get('low_severity', 0))} low)"
        )

    hist_df = snapshot["historical_data"]
    if not hist_df.empty:
        lines.append("\nHistorical financials (all line items, all periods):")
        lines.append(hist_df.to_csv(index=False))

    latest = snapshot["latest_ratios"]
    if not latest.empty:
        lines.append("Most recent period ratios:")
        for _, row in latest.iterrows():
            lines.append(f"  {row['category']} / {row['ratio_name']}: {row['value']:.2f}")

    return "\n".join(lines)


# ---------------------------------------------------------------------
# Agentic tools -- real re-computation, not hallucinated numbers
# ---------------------------------------------------------------------

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "rerun_forecast",
            "description": (
                "Re-projects the income statement, working capital, and cash flow "
                "for N years forward using either the auto-derived assumptions or "
                "user-overridden assumptions (revenue growth rate, COGS % of revenue, "
                "opex % of revenue, tax rate, capex % of revenue). Use this whenever "
                "the user asks a 'what if' question about growth, margins, or costs."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "years_forward": {"type": "integer", "default": 5},
                    "revenue_growth_rate": {"type": "number", "description": "e.g. 0.05 for 5%. Omit to use auto-derived."},
                    "cogs_pct_revenue": {"type": "number", "description": "e.g. 0.55 for 55%. Omit to use auto-derived."},
                    "opex_pct_revenue": {"type": "number", "description": "Omit to use auto-derived."},
                    "tax_rate": {"type": "number", "description": "Omit to use auto-derived."},
                    "capex_pct_revenue": {"type": "number", "description": "Omit to use auto-derived."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rerun_dcf",
            "description": (
                "Re-runs the DCF valuation with a given discount rate and terminal "
                "growth rate on top of the most recently computed forecast (call "
                "rerun_forecast first if the user also wants to change growth/margin "
                "assumptions). Use this for 'what if the discount rate were X' questions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "discount_rate": {"type": "number", "description": "e.g. 0.10 for 10%"},
                    "terminal_growth": {"type": "number", "description": "e.g. 0.025 for 2.5%"},
                },
                "required": ["discount_rate", "terminal_growth"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_stress_test",
            "description": (
                "Applies a stress scenario on top of the auto-derived baseline forecast "
                "and compares the result to that baseline -- equity value impact, minimum "
                "projected cash balance, and whether cash goes negative in any period. Use "
                "this for questions like 'what if revenue dropped 20%', 'what happens if "
                "margins compress', or 'can we survive a rate hike'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "shock_type": {
                        "type": "string",
                        "enum": ["revenue_shock", "margin_compression", "interest_rate_hike"],
                        "description": "revenue_shock: cuts revenue growth. margin_compression: raises COGS % of revenue. interest_rate_hike: raises the DCF discount rate.",
                    },
                    "magnitude": {
                        "type": "number",
                        "description": "Severity as a decimal, e.g. 0.10 for a 10-percentage-point shock, 0.20 for 20. Defaults to 0.10 if omitted.",
                    },
                    "years_forward": {"type": "integer", "default": 5},
                },
                "required": ["shock_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_line_item_history",
            "description": (
                "Looks up the exact historical values for one line item (e.g. "
                "'revenue', 'net_income', 'total_assets') across all uploaded periods. "
                "Use this instead of estimating from memory when the user asks about "
                "a specific number."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "line_item": {"type": "string"},
                },
                "required": ["line_item"],
            },
        },
    },
]


class ChatSession:
    """Holds the mutable state a chat needs across turns: the DB
    connection, which company we're talking about, the last forecast
    the tools produced (so rerun_dcf can reuse it), and message history."""

    def __init__(self, conn, upload_id: str):
        self.conn = conn
        self.upload_id = upload_id
        self.snapshot = build_company_snapshot(conn, upload_id)
        self.messages = []
        self._last_income_projection = None
        self._last_working_capital = None
        self._last_cash_flow = None

    def _system_prompt(self) -> str:
        return (
            "You are a financial analyst assistant embedded in the AI Financial "
            "Intelligence Platform. Answer questions about the company below using "
            "ONLY the data provided or returned by your tools -- never invent or "
            "estimate a number that isn't grounded in the data. If something isn't "
            "available, say so plainly instead of guessing. When a user asks a "
            "'what if' question, use the rerun_forecast / rerun_dcf tools rather "
            "than reasoning about it in prose. For questions about resilience, risk, "
            "downside, or 'what if things went wrong', use run_stress_test instead. "
            "Keep answers concise and quote exact figures with units.\n\n"
            "PARSING NATURAL-LANGUAGE ASSUMPTIONS: rerun_forecast's parameters are "
            "flat rates applied across the whole projection period -- there is no "
            "support for a rate that changes year over year (e.g. '10% tapering to "
            "6%'). When the user describes assumptions in a sentence, extract them "
            "into the tool's flat parameters using this mapping:\n"
            "  - 'grow revenue by X%' / 'X% growth' -> revenue_growth_rate\n"
            "  - 'margins improve to X%' / 'gross margin of X%' -> derive cogs_pct_revenue as (1 - X%)\n"
            "  - 'costs at X% of revenue' / 'COGS of X%' -> cogs_pct_revenue\n"
            "  - 'opex at X%' / 'operating expenses of X%' -> opex_pct_revenue\n"
            "  - 'tax rate of X%' -> tax_rate\n"
            "  - 'capex at X% of revenue' -> capex_pct_revenue\n"
            "If the user gives a range or a trajectory (e.g. 'growing from 10% to 6%'), "
            "pick the AVERAGE of the described range as the single flat rate, and say "
            "explicitly in your reply that you approximated a changing rate as a flat "
            "average because the model doesn't support year-by-year assumptions yet -- "
            "do not silently pick one endpoint without explaining the approximation.\n\n"
            + _snapshot_to_prompt_text(self.snapshot)
        )

    def _run_pipeline(self, assumptions: dict, years_forward: int = 5):
        """Runs income -> working capital -> cash flow for a given set of
        assumptions. Shared by rerun_forecast and run_stress_test so both
        use identical math with zero duplication."""
        hist_df = self.snapshot["historical_data"]

        income_projection = project_income_statement(hist_df, assumptions, years_forward=years_forward)

        wc_assumptions = derive_working_capital_assumptions(hist_df)
        starting_total_assets = get_latest_period_value(hist_df, "total_assets") or 0.0
        starting_current_assets = get_latest_period_value(hist_df, "total_current_assets") or 0.0
        starting_non_current_assets = starting_total_assets - starting_current_assets
        balancing_items = get_balancing_items(hist_df)

        working_capital = project_working_capital(
            income_projection, hist_df, wc_assumptions,
            starting_non_current_assets, balancing_items,
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
        return income_projection, working_capital, cash_flow

    def _execute_tool(self, name: str, tool_input: dict) -> dict:
        hist_df = self.snapshot["historical_data"]

        if name == "get_line_item_history":
            item = tool_input["line_item"]
            row = hist_df[hist_df["line_item"] == item]
            if row.empty:
                return {"error": f"No line item '{item}' found in historical data."}
            return row.to_dict(orient="records")[0]

        if name == "run_stress_test":
            shock_type = tool_input["shock_type"]
            magnitude = tool_input.get("magnitude", 0.10)
            years_forward = tool_input.get("years_forward", 5)

            baseline_assumptions = derive_default_assumptions(hist_df)
            stressed_assumptions = dict(baseline_assumptions)
            discount_rate = 0.10
            stressed_discount_rate = discount_rate

            if shock_type == "revenue_shock":
                stressed_assumptions["revenue_growth_rate"] = baseline_assumptions["revenue_growth_rate"] - magnitude
            elif shock_type == "margin_compression":
                stressed_assumptions["cogs_pct_revenue"] = min(
                    baseline_assumptions["cogs_pct_revenue"] * (1 + magnitude), 0.99
                )
            elif shock_type == "interest_rate_hike":
                stressed_discount_rate = discount_rate + magnitude
            else:
                return {"error": f"Unknown shock_type '{shock_type}'"}

            _, _, baseline_cf = self._run_pipeline(baseline_assumptions, years_forward)
            _, _, stressed_cf = self._run_pipeline(stressed_assumptions, years_forward)

            net_debt = estimate_net_debt(hist_df)
            baseline_dcf = run_dcf(compute_free_cash_flow(baseline_cf), discount_rate, 0.025, net_debt)
            stressed_dcf = run_dcf(compute_free_cash_flow(stressed_cf), stressed_discount_rate, 0.025, net_debt)

            stressed_min_cash = float(stressed_cf["ending_cash"].min())
            cash_breach = stressed_min_cash < 0

            self._last_income_projection, self._last_working_capital, self._last_cash_flow = \
                self._run_pipeline(stressed_assumptions, years_forward)

            return {
                "shock_type": shock_type,
                "magnitude": magnitude,
                "baseline_equity_value": baseline_dcf["equity_value"],
                "stressed_equity_value": stressed_dcf["equity_value"],
                "equity_value_change_pct": round(
                    (stressed_dcf["equity_value"] - baseline_dcf["equity_value"]) / baseline_dcf["equity_value"] * 100, 1
                ) if baseline_dcf["equity_value"] else None,
                "baseline_min_cash": float(baseline_cf["ending_cash"].min()),
                "stressed_min_cash": stressed_min_cash,
                "cash_goes_negative": cash_breach,
            }

        if name == "rerun_forecast":
            years_forward = tool_input.get("years_forward", 5)
            assumptions = derive_default_assumptions(hist_df)
            for key in ("revenue_growth_rate", "cogs_pct_revenue", "opex_pct_revenue",
                        "tax_rate", "capex_pct_revenue"):
                if key in tool_input and tool_input[key] is not None:
                    assumptions[key] = tool_input[key]

            income_projection, working_capital, cash_flow = self._run_pipeline(assumptions, years_forward)

            self._last_income_projection = income_projection
            self._last_working_capital = working_capital
            self._last_cash_flow = cash_flow

            return {
                "assumptions_used": assumptions,
                "income_projection": income_projection.to_dict(orient="records"),
            }

        if name == "rerun_dcf":
            if self._last_cash_flow is None:
                # No prior what-if forecast -- fall back to auto-derived assumptions
                self._execute_tool("rerun_forecast", {})
            fcf_df = compute_free_cash_flow(self._last_cash_flow)
            net_debt = estimate_net_debt(hist_df)
            result = run_dcf(
                fcf_df, tool_input["discount_rate"], tool_input["terminal_growth"], net_debt
            )
            return result

        return {"error": f"Unknown tool '{name}'"}

    def ask(self, user_message: str) -> str:
        """Sends one user message through the tool-use loop and returns
        the assistant's final text reply. Conversation history persists
        on self.messages across calls. Groq's API is OpenAI-compatible:
        the system prompt is a message (not a separate param), and tool
        results go back as role='tool' messages keyed by tool_call_id."""
        client = _get_client()

        # Keep the system prompt fresh (snapshot doesn't change mid-session,
        # but this keeps the pattern simple and correct either way).
        if not self.messages or self.messages[0]["role"] != "system":
            self.messages.insert(0, {"role": "system", "content": self._system_prompt()})
        self.messages.append({"role": "user", "content": user_message})

        for _ in range(MAX_TOOL_ITERATIONS):
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                max_tokens=1500,
                tools=TOOLS,
                messages=self.messages,
            )
            message = response.choices[0].message

            if not message.tool_calls:
                self.messages.append({"role": "assistant", "content": message.content})
                return message.content or ""

            # Model wants to call one or more tools -- execute each and feed results back
            self.messages.append({
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in message.tool_calls
                ],
            })
            for tc in message.tool_calls:
                tool_input = json.loads(tc.function.arguments) if tc.function.arguments else {}
                result = self._execute_tool(tc.function.name, tool_input)
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, default=str),
                })

        return "I wasn't able to finish that request in a reasonable number of steps -- try breaking it into a simpler question."


# ---------------------------------------------------------------------
# Narrative commentary -- single-shot, non-agentic, feeds into the report
# ---------------------------------------------------------------------

def generate_narrative_commentary(report_data: dict) -> str:
    """Takes the same `data` dict that report_generator.gather_report_data()
    produces and writes a short MD&A-style commentary paragraph. Pure
    single completion call -- no tools, no back-and-forth. Meant to be
    inserted into the docx report as an extra section."""
    client = _get_client()

    hist_df = report_data["historical_data"]
    ratios = report_data["ratios"]
    dcf = report_data["dcf_result"]

    prompt = (
        f"Write a concise (150-250 word) Management Discussion & Analysis style "
        f"commentary for {report_data['company_name']}, based strictly on the data "
        f"below. Cover: the revenue/profitability trend, one notable ratio, and the "
        f"headline DCF-implied equity value. Do not invent any figures not present "
        f"below. Plain prose, no headers, no bullet points.\n\n"
        f"Historical financials:\n{hist_df.to_csv(index=False)}\n\n"
        f"Ratios:\n{ratios.to_csv(index=False)}\n\n"
        f"DCF result: {json.dumps(dcf, default=str)}"
    )

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content or ""


# ---------------------------------------------------------------------
# Convenience entry point for a Streamlit chat page
# ---------------------------------------------------------------------

def get_or_create_session(session_state, conn, upload_id: str) -> ChatSession:
    """Streamlit-friendly helper: keeps one ChatSession per upload_id in
    st.session_state so history persists across reruns."""
    key = f"chat_session_{upload_id}"
    if key not in session_state or session_state[key].upload_id != upload_id:
        session_state[key] = ChatSession(conn, upload_id)
    return session_state[key]