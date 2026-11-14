"""
Evaluation script for Phase 2 Header Mapping & Normalization.
Computes precision, recall, and F1-score across labelled messy test files
with different naming conventions (US GAAP, Indian Ind AS, informal abbreviations).
Saves results to evaluation_results.md for direct project report citation.
"""
import sys
from pathlib import Path
from typing import List, Tuple

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.ingestion.schema_matcher import SchemaMatcher


TEST_CASES_INCOME = [
    ("Revenue from operations", "revenue"),
    ("Gross Turnover / Sales", "revenue"),
    ("Direct Operating Costs", "cost_of_goods_sold"),
    ("Cost of Materials Consumed", "cost_of_goods_sold"),
    ("Gross Profit", "gross_profit"),
    ("Selling, General and Administrative", "operating_expenses"),
    ("SG&A Expense", "operating_expenses"),
    ("Research & Development", "research_development"),
    ("Operating Profit (EBIT)", "operating_income"),
    ("Finance costs (interest)", "interest_expense"),
    ("Income before tax", "pretax_income"),
    ("Provision for taxes", "tax_expense"),
    ("Profit for the year (PAT)", "net_income"),
    ("Diluted EPS ($)", "eps_diluted"),
]

TEST_CASES_BALANCE_SHEET = [
    ("Cash and bank balances", "cash_and_equivalents"),
    ("Trade receivables", "accounts_receivable"),
    ("Inventories / Stock-in-trade", "inventory"),
    ("Total current assets", "total_current_assets"),
    ("Property, plant and equipment", "property_plant_equipment"),
    ("Total Assets", "total_assets"),
    ("Trade Payables", "accounts_payable"),
    ("Current Borrowings", "short_term_debt"),
    ("Total current liabilities", "total_current_liabilities"),
    ("Long term debt, net", "long_term_debt"),
    ("Total Liabilities", "total_liabilities"),
    ("Retained Profits", "retained_earnings"),
    ("Total Shareholders' Equity", "total_equity"),
]


def run_evaluation() -> dict:
    matcher_inc = SchemaMatcher("INCOME_STATEMENT")
    matcher_bs = SchemaMatcher("BALANCE_SHEET")

    def evaluate_suite(matcher, test_cases):
        tp = 0
        fp = 0
        fn = 0
        for raw, expected in test_cases:
            proposal = matcher.match_header(raw)
            if proposal.proposed_canonical == expected:
                tp += 1
            else:
                if proposal.proposed_canonical is not None:
                    fp += 1
                else:
                    fn += 1
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        return {
            "total": len(test_cases),
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        }

    res_inc = evaluate_suite(matcher_inc, TEST_CASES_INCOME)
    res_bs = evaluate_suite(matcher_bs, TEST_CASES_BALANCE_SHEET)

    total_tp = res_inc["tp"] + res_bs["tp"]
    total_samples = res_inc["total"] + res_bs["total"]
    overall_accuracy = round(total_tp / total_samples, 4)

    return {
        "income_statement": res_inc,
        "balance_sheet": res_bs,
        "overall_accuracy": overall_accuracy,
        "total_evaluated": total_samples,
    }


def update_results_file(results: dict):
    results_path = PROJECT_ROOT / "evaluation_results.md"
    content = f"""# AI-Powered Financial Intelligence Platform - Formal Evaluation Results

This file records reproducible benchmark metrics evaluated directly over tested components for citation in the project report.

---

## 1. Module: Header Mapping (ETL & Schema Matching)
- **Evaluation Date**: 2026-10-28
- **Algorithm**: Curated Alias Dictionary + RapidFuzz (Token Sort Ratio & Levenshtein Distance)
- **Total Labeled Test Headers**: {results['total_evaluated']}
- **Overall Header Matching Accuracy**: {results['overall_accuracy'] * 100:.2f}%

### Breakdown by Statement Type:
| Statement Type | Test Items | Precision | Recall | F1-Score |
| :--- | :---: | :---: | :---: | :---: |
| **Income Statement** | {results['income_statement']['total']} | {results['income_statement']['precision']:.4f} | {results['income_statement']['recall']:.4f} | {results['income_statement']['f1']:.4f} |
| **Balance Sheet** | {results['balance_sheet']['total']} | {results['balance_sheet']['precision']:.4f} | {results['balance_sheet']['recall']:.4f} | {results['balance_sheet']['f1']:.4f} |

---
"""
    results_path.write_text(content, encoding="utf-8")
    print(f"Evaluation results successfully saved to {results_path}")


if __name__ == "__main__":
    res = run_evaluation()
    print("Evaluation Results:", res)
    update_results_file(res)
