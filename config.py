"""
Central configuration for AI Financial Intelligence Platform
Canonical financial line items + alias dictionary for fuzzy matching
"""
from pathlib import Path

# ---------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent
DATA_RAW = PROJECT_ROOT / "data" / "raw"
DATA_STAGING = PROJECT_ROOT / "data" / "staging"
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
DATA_WAREHOUSE = PROJECT_ROOT / "data" / "warehouse"
DB_PATH = PROJECT_ROOT / "database" / "financial_warehouse.duckdb"
TEMPLATE_PATH = PROJECT_ROOT / "data" / "template_financial_statement.xlsx"

# Fuzzy match confidence thresholds
AUTO_ACCEPT_THRESHOLD = 0.90
SUGGEST_THRESHOLD = 0.60


# ---------------------------------------------------------------------
# Canonical Line Items + Aliases
# ---------------------------------------------------------------------

INCOME_STATEMENT_FIELDS = {
    "revenue": [
        "revenue", "total revenue", "net revenue", "net sales", "sales revenue",
        "sales", "total net sales", "revenue, net", "net operating revenue",
    ],
    "cost_of_goods_sold": [
        "cost of goods sold", "cogs", "cost of sales", "cost of revenue",
        "total cost of revenue", "cost of products sold",
    ],
    "gross_profit": [
        "gross profit", "gross margin", "gross income",
    ],
    "operating_expenses": [
        "operating expenses", "total operating expenses", "opex", "op ex",
        "selling general and administrative", "sg&a", "sga",
    ],
    "research_development": [
        "research and development", "r&d", "research & development expense",
    ],
    "operating_income": [
        "operating income", "income from operations", "operating profit",
        "ebit", "earnings before interest and tax",
    ],
    "interest_expense": [
        "interest expense", "interest expense, net", "net interest expense",
    ],
    "pretax_income": [
        "income before taxes", "pretax income", "earnings before tax",
        "income before provision for income taxes",
    ],
    "tax_expense": [
        "income tax expense", "provision for income taxes", "tax expense",
        "income taxes",
    ],
    "net_income": [
        "net income", "net earnings", "net profit", "net income attributable",
        "profit for the year", "net income (loss)",
    ],
    "eps_basic": [
        "basic earnings per share", "eps basic", "basic eps",
        "earnings per share, basic",
    ],
    "eps_diluted": [
        "diluted earnings per share", "eps diluted", "diluted eps",
        "earnings per share, diluted",
    ],
}

BALANCE_SHEET_FIELDS = {
    "cash_and_equivalents": [
        "cash and cash equivalents", "cash and equivalents", "cash",
        "cash & cash equivalents",
    ],
    "accounts_receivable": [
        "accounts receivable", "trade receivables", "receivables, net",
        "accounts receivable, net",
    ],
    "inventory": [
        "inventory", "inventories", "inventory, net", "merchandise inventory",
    ],
    "total_current_assets": [
        "total current assets", "current assets",
    ],
    "total_assets": [
        "total assets",
    ],
    "accounts_payable": [
        "accounts payable", "trade payables", "accounts payable, trade",
    ],
    "total_current_liabilities": [
        "total current liabilities", "current liabilities",
    ],
    "long_term_debt": [
        "long-term debt", "long term debt", "long-term debt, net",
        "total long-term debt",
    ],
    "total_liabilities": [
        "total liabilities",
    ],
    "total_equity": [
        "total stockholders equity", "total shareholders equity",
        "total equity", "stockholders equity", "total stockholders' equity",
    ],
    "retained_earnings": [
        "retained earnings", "accumulated deficit", "retained earnings (deficit)",
    ],
}

CASH_FLOW_FIELDS = {
    "cash_from_operations": [
        "net cash provided by operating activities", "cash flow from operations",
        "net cash from operating activities", "operating cash flow",
        "cash generated from operations",
    ],
    "capital_expenditures": [
        "capital expenditures", "purchases of property and equipment",
        "capex", "purchase of property, plant and equipment",
    ],
    "cash_from_investing": [
        "net cash used in investing activities", "cash flow from investing",
        "net cash from investing activities",
    ],
    "cash_from_financing": [
        "net cash used in financing activities", "cash flow from financing",
        "net cash from financing activities",
    ],
    "free_cash_flow": [
        "free cash flow", "fcf",
    ],
}

ALL_FIELDS = {
    **INCOME_STATEMENT_FIELDS,
    **BALANCE_SHEET_FIELDS,
    **CASH_FLOW_FIELDS,
}

REQUIRED_FIELDS = [
    "revenue", "net_income", "total_assets", "total_liabilities", "total_equity",
]

YEARS_OF_HISTORY = 5