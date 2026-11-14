"""
Schema matching engine combining:
1. Exact alias dictionary lookup (O(1))
2. Normalized text pre-processing (lowercase, stripped punctuation)
3. Fuzzy matching via RapidFuzz (token_sort_ratio / partial_ratio)
4. Configurable thresholding for auto-accept vs. review required
"""
import re
from typing import List, Optional, Tuple, Dict
from rapidfuzz import fuzz

from app.ingestion.alias_dictionary import CANONICAL_ALIASES
from app.schemas.workflow import MappingProposal
from app.core.logging import get_logger

logger = get_logger(__name__)

# Thresholds
AUTO_ACCEPT_THRESHOLD = 0.90
AMBIGUITY_THRESHOLD = 0.65


def clean_text_label(label: str) -> str:
    """Removes special characters, extra whitespace, footnotes [1], (notes), etc."""
    s = str(label).strip().lower()
    s = re.sub(r"\[\d+\]|\(\d+\)", "", s)  # footnote markers
    s = re.sub(r"[,;:\*\t\n\r]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


class SchemaMatcher:
    """Matches raw spreadsheet line item headers to canonical items."""

    def __init__(self, statement_type: str):
        self.statement_type = statement_type
        self.alias_map: Dict[str, str] = {}
        self.canonical_list: List[str] = []

        statement_aliases = CANONICAL_ALIASES.get(statement_type, {})
        for canonical, aliases in statement_aliases.items():
            self.canonical_list.append(canonical)
            # Add canonical itself
            self.alias_map[clean_text_label(canonical.replace("_", " "))] = canonical
            for a in aliases:
                self.alias_map[clean_text_label(a)] = canonical

    def match_header(self, raw_label: str) -> MappingProposal:
        """
        Evaluates a raw header string and produces a candidate proposal.
        """
        cleaned = clean_text_label(raw_label)
        if not cleaned:
            return MappingProposal(
                raw_label=raw_label,
                proposed_canonical=None,
                statement_type=self.statement_type,
                confidence=0.0,
                method="unknown",
                alternatives=[],
            )

        # 1. Exact alias lookup
        if cleaned in self.alias_map:
            return MappingProposal(
                raw_label=raw_label,
                proposed_canonical=self.alias_map[cleaned],
                statement_type=self.statement_type,
                confidence=1.0,
                method="alias",
                alternatives=[],
            )

        # 2. Fuzzy match against all known aliases
        best_canonical = None
        best_score = 0.0
        scores: Dict[str, float] = {}

        for alias_phrase, canonical in self.alias_map.items():
            # Blend token sort ratio and standard ratio
            score_sort = fuzz.token_sort_ratio(cleaned, alias_phrase) / 100.0
            score_std = fuzz.ratio(cleaned, alias_phrase) / 100.0
            score = max(score_sort, score_std)

            if score > scores.get(canonical, 0.0):
                scores[canonical] = score

        sorted_candidates = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        if sorted_candidates:
            best_canonical, best_score = sorted_candidates[0]
            alternatives = [c for c, s in sorted_candidates[1:4] if s >= AMBIGUITY_THRESHOLD]
        else:
            best_canonical, best_score = None, 0.0
            alternatives = []

        method = "fuzzy"
        if best_score < AMBIGUITY_THRESHOLD:
            # Below threshold -> needs human review or LLM suggestion
            method = "ambiguous"

        return MappingProposal(
            raw_label=raw_label,
            proposed_canonical=best_canonical if best_score >= AMBIGUITY_THRESHOLD else None,
            statement_type=self.statement_type,
            confidence=round(best_score, 3),
            method=method,
            alternatives=alternatives,
        )

    def match_all(self, raw_labels: List[str]) -> List[MappingProposal]:
        """Proposes mappings for a list of raw line items."""
        return [self.match_header(label) for label in raw_labels]
