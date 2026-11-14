"""
Curated alias dictionary for canonical financial line items across statements.
Supports US GAAP, IFRS, and Indian Ind AS reporting conventions.
"""
from app.core.constants import STATEMENT_INCOME, STATEMENT_BALANCE_SHEET, STATEMENT_CASH_FLOW

CANONICAL_ALIASES = {
    # -------------------------------------------------------------
    # INCOME STATEMENT
    # -------------------------------------------------------------
    STATEMENT_INCOME: {
        "revenue": [
            "revenue", "total revenue", "net revenue", "net sales", "sales revenue",
            "sales", "total net sales", "revenue from operations", "operating revenue",
            "gross turnover", "turnover", "total sales",
        ],
        "cost_of_goods_sold": [
            "cost of goods sold", "cogs", "cost of sales", "cost of revenue",
            "total cost of revenue", "cost of products sold", "cost of materials consumed",
            "direct costs",
        ],
        "gross_profit": [
            "gross profit", "gross margin", "gross income",
        ],
        "operating_expenses": [
            "operating expenses", "total operating expenses", "opex", "sg&a",
            "selling, general and administrative", "selling general and administrative",
            "administrative expenses", "operating costs",
        ],
        "research_development": [
            "research and development", "r&d", "research & development expense",
            "r&d expense",
        ],
        "operating_income": [
            "operating income", "income from operations", "operating profit",
            "ebit", "earnings before interest and tax", "operating profit before tax",
        ],
        "depreciation_amortization": [
            "depreciation and amortization", "d&a", "depreciation & amortisation",
            "depreciation expense", "amortization expense",
        ],
        "interest_expense": [
            "interest expense", "net interest expense", "interest and debt expense",
            "finance costs", "interest cost",
        ],
        "interest_income": [
            "interest income", "finance income", "interest and dividend income",
        ],
        "pretax_income": [
            "income before income taxes", "pretax income", "earnings before tax",
            "profit before tax", "pbt", "income before taxes",
        ],
        "tax_expense": [
            "income tax expense", "provision for income taxes", "tax expense",
            "current tax", "taxes on income",
        ],
        "net_income": [
            "net income", "net earnings", "net profit", "profit for the year",
            "profit after tax", "pat", "net income attributable to shareholders",
        ],
        "eps_diluted": [
            "diluted earnings per share", "diluted eps", "eps diluted", "diluted net income per share",
        ],
    },

    # -------------------------------------------------------------
    # BALANCE SHEET
    # -------------------------------------------------------------
    STATEMENT_BALANCE_SHEET: {
        "cash_and_equivalents": [
            "cash and cash equivalents", "cash & cash equivalents", "cash and equivalents",
            "cash and bank balances", "cash",
        ],
        "short_term_investments": [
            "marketable securities", "short-term investments", "current investments",
        ],
        "accounts_receivable": [
            "accounts receivable", "trade receivables", "receivables, net",
            "trade and other receivables", "accounts receivable, net",
        ],
        "inventory": [
            "inventory", "inventories", "inventory, net", "merchandise inventory",
            "stock-in-trade",
        ],
        "total_current_assets": [
            "total current assets", "current assets",
        ],
        "property_plant_equipment": [
            "property, plant and equipment, net", "ppe", "property, plant and equipment",
            "net ppe", "tangible assets", "fixed assets",
        ],
        "total_assets": [
            "total assets",
        ],
        "accounts_payable": [
            "accounts payable", "trade payables", "accounts payable, trade",
            "trade and other payables",
        ],
        "short_term_debt": [
            "short-term debt", "short term debt", "current portion of long-term debt",
            "current borrowings", "short-term borrowings",
        ],
        "total_current_liabilities": [
            "total current liabilities", "current liabilities",
        ],
        "long_term_debt": [
            "long-term debt", "long term debt", "long-term borrowings",
            "non-current debt", "total long-term debt",
        ],
        "total_liabilities": [
            "total liabilities",
        ],
        "retained_earnings": [
            "retained earnings", "accumulated deficit", "retained profits",
        ],
        "total_equity": [
            "total stockholders' equity", "total shareholders' equity", "total equity",
            "stockholders' equity", "shareholders' funds", "equity attributable to owners",
        ],
        "total_liabilities_and_equity": [
            "total liabilities and stockholders' equity", "total liabilities and equity",
            "total liabilities and shareholders' equity",
        ],
    },

    # -------------------------------------------------------------
    # CASH FLOW STATEMENT
    # -------------------------------------------------------------
    STATEMENT_CASH_FLOW: {
        "net_income": [
            "net income", "net profit", "profit for the period",
        ],
        "depreciation_amortization": [
            "depreciation and amortization", "d&a", "depreciation & amortisation",
        ],
        "operating_cash_flow": [
            "net cash provided by operating activities", "operating cash flow",
            "cash flow from operations", "cash generated from operations",
            "net cash from operating activities",
        ],
        "capital_expenditures": [
            "capital expenditures", "capex", "payments for property, plant and equipment",
            "additions to property and equipment", "purchase of fixed assets",
        ],
        "investing_cash_flow": [
            "net cash used in investing activities", "investing cash flow",
            "net cash from investing activities",
        ],
        "debt_repayment": [
            "repayments of long-term debt", "repayment of borrowings", "principal payments",
        ],
        "debt_issuance": [
            "proceeds from issuance of long-term debt", "proceeds from borrowings",
        ],
        "dividends_paid": [
            "dividends paid", "payments for dividends", "dividend distributions",
        ],
        "financing_cash_flow": [
            "net cash used in financing activities", "financing cash flow",
            "net cash from financing activities",
        ],
        "net_change_in_cash": [
            "net increase (decrease) in cash and cash equivalents", "net change in cash",
            "net increase in cash and equivalents",
        ],
    },
}
