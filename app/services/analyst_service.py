"""
Analyst Coordinator Service:
Takes user questions, runs the QuestionClassifier, invokes TypedFinancialQueryTools,
builds the EvidenceBundle, and runs GroundedAnalyst to produce verifiable answers.
"""
from typing import Dict, Any, Optional
import duckdb

from app.analyst.classifier import QuestionClassifier
from app.analyst.query_tools import TypedFinancialQueryTools, EvidenceBundle, EvidenceItem
from app.analyst.grounded_analyst import GroundedAnalyst
from app.database.connection import db_manager


class AnalystService:
    """Service mediating question processing and evidence retrieval."""

    def __init__(self, conn: Optional[duckdb.DuckDBPyConnection] = None):
        self.conn = conn or db_manager.get_connection()
        self.tools = TypedFinancialQueryTools(self.conn)

    def answer_question(
        self,
        company_id: str,
        question: str,
        dataset_version: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Coordinates full QA lifecycle:
        1. Classify intent
        2. Resolve items & periods
        3. Query typed facts from DuckDB
        4. Check for missing evidence & format EvidenceBundle
        5. Generate response with citations or abstain
        """
        intent = QuestionClassifier.classify_intent(question)
        periods = QuestionClassifier.extract_periods(question)
        canonical_item = QuestionClassifier.extract_canonical_item(question)

        bundle = EvidenceBundle(
            query_intent=intent,
            company_id=company_id,
            dataset_version=dataset_version,
        )

        if intent == "unsupported":
            bundle.is_sufficient = False
            bundle.abstention_reason = "the platform provides research and education analysis only and does not generate trade execution or investment advice."
            ans = GroundedAnalyst.generate_grounded_answer(bundle, question)
            return {"answer": ans, "bundle": bundle.model_dump(), "intent": intent}

        if intent == "valuation":
            val_data = self.tools.get_latest_valuation(company_id)
            if not val_data:
                bundle.is_sufficient = False
                bundle.abstention_reason = f"no completed DCF valuation run was found for company '{company_id}'."
            else:
                bundle.derived_metrics = {
                    "enterprise_value": val_data["enterprise_value"],
                    "equity_value": val_data["equity_value"],
                    "wacc": val_data["wacc"],
                    "terminal_growth": val_data["terminal_growth_rate"],
                    "implied_share_price": val_data["implied_share_price"],
                }
            ans = GroundedAnalyst.generate_grounded_answer(bundle, question)
            return {"answer": ans, "bundle": bundle.model_dump(), "intent": intent}

        if intent == "scenario":
            val_data = self.tools.get_latest_valuation(company_id)
            if not val_data or not val_data.get("scenarios"):
                bundle.is_sufficient = False
                bundle.abstention_reason = f"no scenario analysis results are available for company '{company_id}'."
            else:
                bundle.derived_metrics = val_data["scenarios"]
            ans = GroundedAnalyst.generate_grounded_answer(bundle, question)
            return {"answer": ans, "bundle": bundle.model_dump(), "intent": intent}

        # Factual or Trend
        if not canonical_item:
            bundle.is_sufficient = False
            bundle.abstention_reason = "the financial line item could not be identified from your query."
            ans = GroundedAnalyst.generate_grounded_answer(bundle, question)
            return {"answer": ans, "bundle": bundle.model_dump(), "intent": intent}

        if periods:
            # Query specific periods
            found_items = []
            for p in periods:
                fact = self.tools.get_line_item(company_id, canonical_item, p, dataset_version)
                if fact:
                    found_items.append(fact)
            if not found_items:
                bundle.is_sufficient = False
                bundle.abstention_reason = f"no reported facts were found for '{canonical_item}' in period(s): {', '.join(periods)}."
            else:
                bundle.items = found_items
        else:
            # Query entire series
            series = self.tools.get_line_item_history(company_id, canonical_item)
            if not series:
                bundle.is_sufficient = False
                bundle.abstention_reason = f"no historical facts were found for '{canonical_item}'."
            else:
                bundle.items = series
                if len(series) >= 2:
                    v_start = series[0].normalized_value
                    v_end = series[-1].normalized_value
                    years = len(series) - 1
                    if v_start > 0 and v_end > 0 and years > 0:
                        cagr = (v_end / v_start) ** (1.0 / years) - 1.0
                        bundle.derived_metrics["cagr"] = round(cagr, 4)

        ans = GroundedAnalyst.generate_grounded_answer(bundle, question)
        return {"answer": ans, "bundle": bundle.model_dump(), "intent": intent}
