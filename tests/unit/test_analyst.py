"""
Unit Tests for Phase 6 Grounded AI Analyst:
1. Question classification into factual, ratio, trend, valuation, and unsupported categories.
2. Typed parameterized queries over DuckDB (no text-to-SQL).
3. Evidence bundle assembly with exact provenance citations.
4. Strict abstention when requested periods or companies are absent.
5. Out-of-scope question rejection with educational disclaimer.
"""
import pytest
from app.analyst.classifier import QuestionClassifier
from app.analyst.query_tools import TypedFinancialQueryTools
from app.services.analyst_service import AnalystService
from app.core.constants import DISCLAIMER_SHORT


def test_question_classifier_intents():
    """Verify question classifier correctly identifies financial intents."""
    assert QuestionClassifier.classify_intent("What was total revenue in 2022?") == "factual"
    assert QuestionClassifier.classify_intent("What is the gross margin for 2023?") == "ratio"
    assert QuestionClassifier.classify_intent("Show me the revenue growth trend over the last 3 years") == "trend"
    assert QuestionClassifier.classify_intent("What is the intrinsic value and DCF valuation?") == "valuation"
    assert QuestionClassifier.classify_intent("What are the bull and bear case scenarios?") == "scenario"
    assert QuestionClassifier.classify_intent("Should I buy or sell this stock now?") == "unsupported"

    # Period extraction
    assert QuestionClassifier.extract_periods("Compare 2021 and 2023") == ["2021", "2023"]
    assert QuestionClassifier.extract_periods("Results for 2022-Q3") == ["2022-Q3"]

    # Canonical mapping
    assert QuestionClassifier.extract_canonical_item("What was sales in 2022?") == "revenue"
    assert QuestionClassifier.extract_canonical_item("What was operating profit?") == "operating_income"


def test_grounded_factual_answer_with_citations(memory_db):
    """Verify factual question retrieves exact fact and produces citation reference."""
    conn = memory_db
    # Seed company, upload, dataset, and financial fact
    conn.execute("INSERT INTO companies (company_id, name) VALUES ('co_grounded', 'Grounded Inc')")
    conn.execute("INSERT INTO uploads (upload_id, company_id, filename, file_hash, file_size_bytes) VALUES ('up_g', 'co_grounded', 'filing_2023.csv', 'hash_g', 500)")
    conn.execute("INSERT INTO datasets (dataset_id, company_id, statement_type) VALUES ('ds_g', 'co_grounded', 'INCOME_STATEMENT')")
    conn.execute("INSERT INTO dataset_versions (dataset_id, version, upload_id, status, is_active) VALUES ('ds_g', 1, 'up_g', 'approved', TRUE)")
    conn.execute(
        """
        INSERT INTO financial_facts (
            fact_id, dataset_id, dataset_version, statement_type, canonical_item,
            period, original_label, original_value, original_unit, original_currency,
            normalized_value, normalized_currency, source_file, source_row
        ) VALUES ('fact_g1', 'ds_g', 1, 'INCOME_STATEMENT', 'revenue', '2023', 'Total Revenue', 450.0, 'millions', 'USD', 450000000.0, 'USD', 'filing_2023.csv', 5)
        """
    )

    service = AnalystService(conn)
    resp = service.answer_question("co_grounded", "What was revenue in 2023?")
    ans = resp["answer"]

    # Must contain exact figure
    assert "450,000,000.00" in ans
    # Must cite file and row provenance
    assert "filing_2023.csv" in ans
    assert "row 5" in ans
    # Must append disclaimer
    assert DISCLAIMER_SHORT in ans


def test_strict_abstention_on_missing_period(memory_db):
    """
    Verify non-negotiable rule:
    When user asks for a period not present in DuckDB (e.g. 2018),
    system MUST abstain rather than hallucinating or guessing.
    """
    conn = memory_db
    conn.execute("INSERT INTO companies (company_id, name) VALUES ('co_abstain', 'Abstain Co')")
    conn.execute("INSERT INTO uploads (upload_id, company_id, filename, file_hash, file_size_bytes) VALUES ('up_a', 'co_abstain', 'file.csv', 'hash_a', 200)")
    conn.execute("INSERT INTO datasets (dataset_id, company_id, statement_type) VALUES ('ds_a', 'co_abstain', 'INCOME_STATEMENT')")
    conn.execute("INSERT INTO dataset_versions (dataset_id, version, upload_id, status, is_active) VALUES ('ds_a', 1, 'up_a', 'approved', TRUE)")
    # Fact exists for 2023 ONLY
    conn.execute(
        """
        INSERT INTO financial_facts (
            fact_id, dataset_id, dataset_version, statement_type, canonical_item,
            period, original_label, original_value, normalized_value, source_file
        ) VALUES ('fact_a1', 'ds_a', 1, 'INCOME_STATEMENT', 'revenue', '2023', 'Revenue', 100.0, 100.0, 'file.csv')
        """
    )

    service = AnalystService(conn)
    # User explicitly asks for 2018 (missing!)
    resp = service.answer_question("co_abstain", "What was net income in 2018?")
    ans = resp["answer"]

    # Must abstain clearly
    assert "I cannot answer this question because" in ans
    assert "not present in the stored records" in ans or "no reported facts" in ans
    assert DISCLAIMER_SHORT in ans


def test_rejection_of_unsupported_investment_advice(memory_db):
    """Verify system strictly rejects trading advice questions."""
    service = AnalystService(memory_db)
    resp = service.answer_question("co_test", "Give me a trading signal or should I buy or sell this stock?")
    ans = resp["answer"]

    assert "I cannot answer this question because" in ans
    assert "research and education analysis only" in ans
