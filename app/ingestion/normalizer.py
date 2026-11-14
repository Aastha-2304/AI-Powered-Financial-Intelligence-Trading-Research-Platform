"""
Financial data normalizer:
Normalizes values to standard base units (e.g., thousands -> *1000, millions -> *1e6, crores -> *1e7),
cleans string amounts with parentheses or minus signs, and formats canonical periods.
"""
import re
from typing import Tuple, Optional, Any
import pandas as pd
from app.core.constants import UNIT_SCALES

# Regex for currency symbols and scale indicators
SCALE_PATTERNS = {
    "thousands": re.compile(r"\b(?:in\s+)?(?:thousands|000s|'000)\b", re.IGNORECASE),
    "millions": re.compile(r"\b(?:in\s+)?(?:millions|m|mn)\b", re.IGNORECASE),
    "billions": re.compile(r"\b(?:in\s+)?(?:billions|b|bn)\b", re.IGNORECASE),
    "crores": re.compile(r"\b(?:in\s+)?(?:crores|cr)\b", re.IGNORECASE),
    "lakhs": re.compile(r"\b(?:in\s+)?(?:lakhs|lac|lacs)\b", re.IGNORECASE),
}

CURRENCY_PATTERNS = {
    "USD": re.compile(r"\$|\busd\b", re.IGNORECASE),
    "INR": re.compile(r"₹|\brs\.?|\binr\b", re.IGNORECASE),
    "EUR": re.compile(r"€|\beur\b", re.IGNORECASE),
    "GBP": re.compile(r"£|\bgbp\b", re.IGNORECASE),
}


class FinancialNormalizer:
    """Normalizes raw financial strings, signs, currencies, and units."""

    @classmethod
    def parse_numeric_value(cls, raw: Any) -> Optional[float]:
        """
        Parses numeric financial value from floats, ints, or messy formatted strings:
        e.g., '(1,234.50)' -> -1234.50, ' - ' or '-' -> 0.0, '$ 45,000' -> 45000.0
        """
        if raw is None:
            return None
        if isinstance(raw, (int, float)):
            if pd.isna(raw):
                return None
            return float(raw)

        s = str(raw).strip()
        if not s or s in {"-", "—", "N/A", "na", "null", "."}:
            return 0.0

        # Remove currency symbols and spaces
        s = re.sub(r"[\$₹€£,\s]", "", s)

        # Check for parentheses indicating negative values e.g. (123.45)
        is_negative = False
        if s.startswith("(") and s.endswith(")"):
            is_negative = True
            s = s[1:-1].strip()
        elif s.startswith("-"):
            is_negative = True
            s = s[1:].strip()

        try:
            val = float(s)
            return -val if is_negative else val
        except ValueError:
            return None

    @classmethod
    def detect_unit_and_currency(cls, text_context: str) -> Tuple[str, float, str]:
        """
        Detects unit scale (e.g. millions) and currency (e.g. USD) from text/headers.
        Returns (unit_name, scaling_factor, currency).
        """
        detected_unit = "ones"
        factor = 1.0
        detected_curr = "USD"

        for unit_name, pattern in SCALE_PATTERNS.items():
            if pattern.search(text_context):
                detected_unit = unit_name
                factor = UNIT_SCALES.get(unit_name, 1.0)
                break

        for curr_name, pattern in CURRENCY_PATTERNS.items():
            if pattern.search(text_context):
                detected_curr = curr_name
                break

        return detected_unit, factor, detected_curr

    @classmethod
    def normalize_value(cls, raw_val: Any, scaling_factor: float = 1.0) -> Tuple[Optional[float], Optional[float]]:
        """
        Converts raw reported value to normalized base scale.
        Returns (original_numeric, normalized_numeric).
        """
        parsed = cls.parse_numeric_value(raw_val)
        if parsed is None:
            return None, None
        normalized = parsed * scaling_factor
        return parsed, normalized
