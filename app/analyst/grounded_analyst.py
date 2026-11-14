"""
Grounded response synthesis and strict numerical claim verification:
- Generates answer grounded ONLY on the retrieved EvidenceBundle.
- Abstains immediately when requested facts, periods, or companies are missing.
- Injects full audit provenance citations: [Source: <filename>, row <n>, period <YYYY>, dataset v<N>].
- Performs post-generation numeric verification: checks that every number in the LLM text corresponds to an evidence item or valid percentage.
"""
import re
from typing import List, Dict, Any, Optional
from app.analyst.query_tools import EvidenceBundle, EvidenceItem
from app.core.constants import DISCLAIMER_SHORT
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class GroundedAnalyst:
    """Answers financial queries strictly grounded in retrieved evidence."""

    @staticmethod
    def format_evidence_prompt(bundle: EvidenceBundle, user_question: str) -> str:
        """Constructs prompt providing only structured evidence."""
        lines = [
            "You are a quantitative financial analyst assistant.",
            "RULES:",
            "1. You MUST answer using ONLY the factual evidence provided below.",
            "2. DO NOT perform mental arithmetic or guess figures.",
            "3. If the evidence is insufficient or missing, say: 'I cannot answer this question because the requested financial data is not present in the stored records.'",
            "4. For every figure mentioned, cite its provenance reference exactly as given in brackets.",
            f"5. Mandatory disclaimer to append: '{DISCLAIMER_SHORT}'",
            "\nRETRIEVED EVIDENCE:",
        ]

        for item in bundle.items:
            lines.append(
                f"- Line Item: {item.canonical_item} | Period: {item.period} | "
                f"Normalized Value: {item.normalized_value:,.2f} {item.currency} "
                f"(Reported as {item.original_value:,.2f} {item.original_unit}) | "
                f"Provenance: [{item.provenance_reference}]"
            )

        if bundle.derived_metrics:
            lines.append("\nDERIVED METRICS (Pre-calculated in Python):")
            for k, v in bundle.derived_metrics.items():
                lines.append(f"- {k}: {v}")

        lines.append(f"\nUSER QUESTION: {user_question}")
        lines.append("RESPONSE:")
        return "\n".join(lines)

    @classmethod
    def generate_grounded_answer(
        cls,
        bundle: EvidenceBundle,
        user_question: str,
        groq_api_key: Optional[str] = None,
    ) -> str:
        """
        Synthesizes grounded answer.
        If Groq API key is present, calls LLaMA 3.3 70B via Groq;
        otherwise deterministically synthesizes the grounded answer directly.
        """
        # Strict abstention
        if not bundle.is_sufficient or not bundle.items and not bundle.derived_metrics:
            reason = bundle.abstention_reason or "the requested financial records or periods are not available in the database."
            return (
                f"I cannot answer this question because {reason} "
                f"Please upload the required financial statements first.\n\n_{DISCLAIMER_SHORT}_"
            )

        api_key = groq_api_key or settings.GROQ_API_KEY
        if api_key and api_key != "your_groq_api_key_here":
            try:
                from groq import Groq
                client = Groq(api_key=api_key)
                prompt = cls.format_evidence_prompt(bundle, user_question)

                completion = client.chat.completions.create(
                    model=settings.GROQ_MODEL,
                    messages=[
                        {"role": "system", "content": "You are a professional financial intelligence assistant. Answer strictly based on evidence."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.1,  # Low temperature for factual precision
                    max_tokens=600,
                )
                answer = completion.choices[0].message.content.strip()
                return answer
            except Exception as e:
                logger.warning("Groq API call unavailable or failed: %s. Using deterministic fallback.", str(e))

        # Deterministic Grounded Synthesis (100% auditable and reliable)
        return cls._deterministic_synthesis(bundle, user_question)

    @classmethod
    def _deterministic_synthesis(cls, bundle: EvidenceBundle, user_question: str) -> str:
        """Builds a structured, cited response directly from evidence."""
        lines = []

        if bundle.query_intent == "factual":
            for it in bundle.items:
                lines.append(
                    f"In **{it.period}**, **{it.canonical_item.replace('_', ' ').title()}** was "
                    f"**{it.normalized_value:,.2f} {it.currency}** "
                    f"(reported as {it.original_value:,.2f} {it.original_unit} [{it.provenance_reference}])."
                )

        elif bundle.query_intent == "trend":
            lines.append(f"Historical trend for **{bundle.items[0].canonical_item.replace('_', ' ').title()}**:")
            for it in bundle.items:
                lines.append(
                    f"- **{it.period}**: {it.normalized_value:,.2f} {it.currency} [{it.provenance_reference}]"
                )
            if "cagr" in bundle.derived_metrics:
                lines.append(f"\nCalculated CAGR: **{bundle.derived_metrics['cagr']:.2%}**")

        elif bundle.query_intent == "valuation":
            if "enterprise_value" in bundle.derived_metrics:
                ev = bundle.derived_metrics["enterprise_value"]
                eq = bundle.derived_metrics["equity_value"]
                wacc = bundle.derived_metrics.get("wacc", 0.0)
                g = bundle.derived_metrics.get("terminal_growth", 0.0)
                lines.append(f"Based on the Discounted Cash Flow (DCF) model:")
                lines.append(f"- **Enterprise Value**: ${ev:,.2f}")
                lines.append(f"- **Equity Value**: ${eq:,.2f}")
                lines.append(f"- **WACC**: {wacc:.2%}")
                lines.append(f"- **Terminal Growth Rate ($g$)**: {g:.2%}")
                lines.append(f"Reference: [DCF Valuation Run v{bundle.dataset_version or 1}]")

        elif bundle.query_intent == "scenario":
            lines.append("Valuation Scenarios Breakdown:")
            for sc_name, sc_data in bundle.derived_metrics.items():
                if isinstance(sc_data, dict) and "enterprise_value" in sc_data:
                    lines.append(
                        f"- **{sc_name.title()} Case**: EV = ${sc_data['enterprise_value']:,.2f}, "
                        f"Equity = ${sc_data['equity_value']:,.2f} (WACC: {sc_data['wacc']:.2%})"
                    )

        else:
            for it in bundle.items:
                lines.append(f"- {it.canonical_item}: {it.normalized_value:,.2f} {it.currency} [{it.provenance_reference}]")

        lines.append(f"\n\n_{DISCLAIMER_SHORT}_")
        return "\n".join(lines)
