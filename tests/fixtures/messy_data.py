"""
Messy test fixture containing:
- Different/unconventional headers ("Revenue from operations", "Direct Operating Costs", "Operating Profit / EBIT")
- Parentheses for negative figures e.g. (120.5)
- Unit declared as In Millions USD
- Missing periods / non-standard column titles
"""
MESSY_INCOME_CSV = """Income Statement (in Millions USD),FY 2021,FY 2022,FY 2023
Revenue from operations,1000.5,1250.0,1500.0
Direct Operating Costs,(600.0),(720.0),(850.0)
Gross Income,400.5,530.0,650.0
Selling General and Admin Expense,150.0,180.0,210.0
Research & Development,50.0,60.0,75.0
Operating Profit (EBIT),200.5,290.0,365.0
Finance costs (interest),20.0,25.0,30.0
Earnings Before Tax,180.5,265.0,335.0
Provision for taxes,45.0,66.0,84.0
Profit for the year (PAT),135.5,199.0,251.0
"""

MESSY_BALANCE_SHEET_CSV = """Balance Sheet (in Thousands USD),2022,2023
Cash and cash equivalents,50000,75000
Trade Receivables,120000,140000
Inventories,80000,95000
Total Current Assets,250000,310000
Property Plant & Equipment (Net),400000,450000
Total Assets,650000,760000
Trade Payables,90000,105000
Short Term Borrowings,30000,25000
Total Current Liabilities,120000,130000
Long-Term Borrowings,200000,220000
Total Liabilities,320000,350000
Retained Earnings,230000,310000
Total Stockholders' Equity,330000,410000
Total Liabilities and Stockholders' Equity,650000,760000
"""
