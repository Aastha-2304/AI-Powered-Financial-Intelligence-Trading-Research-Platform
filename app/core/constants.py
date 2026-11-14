"""
Core constants for AI Financial Intelligence Platform.
Defines the mandatory research/education disclaimer and canonical financial schema keys.
"""

# Non-negotiable regulatory disclaimer shown in UI and all report artifacts
DISCLAIMER_TEXT = (
    "DISCLAIMER: This platform is designed strictly for research, academic, and educational analysis. "
    "The projections, intrinsic valuations, and AI interpretations generated are deterministic model estimates "
    "and do not constitute financial advice, investment recommendations, or trade solicitations."
)

DISCLAIMER_SHORT = "For academic and research purposes only. Not investment advice."

# Canonical statement types
STATEMENT_INCOME = "INCOME_STATEMENT"
STATEMENT_BALANCE_SHEET = "BALANCE_SHEET"
STATEMENT_CASH_FLOW = "CASH_FLOW"

STATEMENT_TYPES = [
    STATEMENT_INCOME,
    STATEMENT_BALANCE_SHEET,
    STATEMENT_CASH_FLOW,
]

# Canonical currency keys
DEFAULT_CURRENCY = "USD"
SUPPORTED_CURRENCIES = ["USD", "INR", "EUR", "GBP"]

# Canonical scale factors
UNIT_SCALES = {
    "ones": 1.0,
    "thousands": 1_000.0,
    "millions": 1_000_000.0,
    "billions": 1_000_000_000.0,
    "lakhs": 100_000.0,
    "crores": 10_000_000.0,
}
