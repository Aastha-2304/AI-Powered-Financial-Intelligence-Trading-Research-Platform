"""
Intent classification and entity/period resolution for the Grounded AI Analyst:
- Classifies user questions into distinct intents:
  1. factual (e.g. "What was revenue in 2022?")
  2. ratio (e.g. "What was the gross margin in 2023?")
  3. trend (e.g. "How has net income changed over the last 3 years?")
  4. valuation / dcf (e.g. "What is the intrinsic value or DCF enterprise value?")
  5. scenario (e.g. "What are the bull and bear case valuations?")
  6. unsupported (e.g. questions asking for trading signals or out-of-scope advice)
- Extracts targeted fiscal period(s) and canonical line items.
- Strict abstention when facts or periods are not present in DuckDB.
"""
import re
from typing import Tuple, List, Optional, Dict, Any
from app.ingestion.statement_detector import PERIOD_YEAR_REGEX, PERIOD_QUARTER_REGEX
from app.ingestion.alias_dictionary import CANONICAL_ALIASES
from app.ingestion.schema_matcher import clean_text_label


class QuestionClassifier:
    """Classifies user queries and resolves canonical items and periods."""

    @staticmethod
    def classify_intent(question: str) -> str:
        q_lower = question.lower()

        # Check for out-of-scope / unsupported
        if any(term in q_lower for term in ["buy or sell", "trading signal", "portfolio optimization", "investing advice"]):
            return "unsupported"

        # Valuation / DCF
        if any(term in q_lower for term in ["valuation", "dcf", "enterprise value", "intrinsic value", "wacc", "fair value", "terminal value"]):
            return "valuation"

        # Scenarios
        if any(term in q_lower for term in ["bull", "bear", "scenario", "sensitivity"]):
            return "scenario"

        # Ratios
        if any(term in q_lower for term in ["margin", "ratio", "dso", "dio", "return on", "roe", "roa"]):
            return "ratio"

        # Trends
        if any(term in q_lower for term in ["trend", "growth", "cagr", "change over time", "evolution"]):
            return "trend"

        return "factual"

    @staticmethod
    def extract_periods(question: str) -> List[str]:
        """Extracts all quarters and distinct annual years mentioned in the question."""
        periods = []
        # Find quarters like 2022-Q3, 2022Q3, Q3-2022
        q_matches = re.finditer(r"\b(19\d\d|20\d\d)[-_ ]?[Qq]([1-4])\b|\b[Qq]([1-4])[-_ ]?(19\d\d|20\d\d)\b", question)
        matched_quarter_years = set()
        for q in q_matches:
            g = q.groups()
            if g[0] and g[1]:
                year_part, qtr_part = g[0], g[1]
            else:
                year_part, qtr_part = g[3], g[2]
            p_str = f"{year_part}-Q{qtr_part}"
            if p_str not in periods:
                periods.append(p_str)
                matched_quarter_years.add(year_part)

        # Find 4-digit years not already matched in quarterly patterns
        y_matches = re.findall(r"\b(19\d\d|20\d\d)\b", question)
        for y in y_matches:
            if y not in matched_quarter_years and y not in periods:
                periods.append(y)

        return sorted(periods)

    @staticmethod
    def extract_canonical_item(question: str) -> Optional[str]:
        """Maps query keywords to canonical line item."""
        cleaned = clean_text_label(question)

        # Quick checks for common financial terms
        keyword_map = {
            "revenue": "revenue",
            "sales": "revenue",
            "turnover": "revenue",
            "cost of goods": "cost_of_goods_sold",
            "cogs": "cost_of_goods_sold",
            "gross profit": "gross_profit",
            "gross margin": "gross_profit",
            "operating expense": "operating_expenses",
            "opex": "operating_expenses",
            "operating income": "operating_income",
            "operating profit": "operating_income",
            "ebit": "operating_income",
            "net income": "net_income",
            "profit": "net_income",
            "earnings": "net_income",
            "total asset": "total_assets",
            "assets": "total_assets",
            "cash": "cash_and_equivalents",
            "receivable": "accounts_receivable",
            "inventory": "inventory",
            "current asset": "total_current_assets",
            "current liabilit": "total_current_liabilities",
            "total liabilit": "total_liabilities",
            "liabilities": "total_liabilities",
            "debt": "long_term_debt",
            "equity": "total_equity",
            "operating cash flow": "operating_cash_flow",
            "free cash flow": "free_cash_flow",
            "fcf": "free_cash_flow",
        }

        for kw, item in keyword_map.items():
            if kw in cleaned:
                return item

        return None
