"""
Transform module for AI Financial Intelligence Platform
Fuzzy-matches messy uploaded line-item labels to canonical financial fields.
"""
import sys
from pathlib import Path
import pandas as pd
from rapidfuzz import fuzz, process

sys.stdout.reconfigure(encoding="utf-8")

# so this file can find config.py at the project root when run from etl/
sys.path.append(str(Path(__file__).resolve().parent.parent))
from config import ALL_FIELDS, AUTO_ACCEPT_THRESHOLD, SUGGEST_THRESHOLD


def _normalize_label(label: str) -> str:
    """Lowercase, strip punctuation/whitespace for consistent matching."""
    label = str(label).lower().strip()
    label = label.replace("&", "and")
    label = label.replace(",", "").replace(".", "").replace("'", "")
    label = " ".join(label.split())  # collapse multiple spaces
    return label


def _build_alias_lookup() -> dict:
    """
    Flatten config.py's ALL_FIELDS dict into {alias: canonical_field}
    for exact-match lookups before falling back to fuzzy matching.
    """
    lookup = {}
    for canonical_field, aliases in ALL_FIELDS.items():
        for alias in aliases:
            lookup[_normalize_label(alias)] = canonical_field
    return lookup


ALIAS_LOOKUP = _build_alias_lookup()
ALL_ALIASES = list(ALIAS_LOOKUP.keys())


def match_label(raw_label: str) -> dict:
    """
    Match a single raw label to a canonical field.
    Returns: {raw_label, canonical_field, confidence, match_type}
    match_type is one of: 'exact', 'fuzzy_auto', 'fuzzy_suggest', 'unmatched'
    """
    normalized = _normalize_label(raw_label)

    # 1. exact match against known aliases
    if normalized in ALIAS_LOOKUP:
        return {
            "raw_label": raw_label,
            "canonical_field": ALIAS_LOOKUP[normalized],
            "confidence": 1.0,
            "match_type": "exact",
        }

    # 2. fuzzy match against all known aliases
    best_match = process.extractOne(normalized, ALL_ALIASES, scorer=fuzz.token_set_ratio)
    if best_match is None:
        return {
            "raw_label": raw_label,
            "canonical_field": None,
            "confidence": 0.0,
            "match_type": "unmatched",
        }

    matched_alias, score, _ = best_match
    confidence = score / 100.0
    canonical_field = ALIAS_LOOKUP[matched_alias]

    if confidence >= AUTO_ACCEPT_THRESHOLD:
        match_type = "fuzzy_auto"
    elif confidence >= SUGGEST_THRESHOLD:
        match_type = "fuzzy_suggest"
    else:
        return {
            "raw_label": raw_label,
            "canonical_field": None,
            "confidence": confidence,
            "match_type": "unmatched",
        }

    return {
        "raw_label": raw_label,
        "canonical_field": canonical_field,
        "confidence": round(confidence, 3),
        "match_type": match_type,
    }


def map_raw_dataframe(df: pd.DataFrame, label_column: str = None) -> pd.DataFrame:
    """
    Takes a raw financial statement DataFrame (line items in the first
    column, periods as remaining columns) and returns a mapping table:
    one row per line item, showing what canonical field it matched to.
    """
    if label_column is None:
        label_column = df.columns[0]

    results = []
    for raw_label in df[label_column].dropna():
        match = match_label(raw_label)
        results.append(match)

    return pd.DataFrame(results)


def apply_mapping(df: pd.DataFrame, mapping: pd.DataFrame, label_column: str = None) -> pd.DataFrame:
    """
    Applies a confirmed mapping to the raw DataFrame, renaming the label
    column values to canonical field names. Only keeps rows that were
    matched (unmatched rows are dropped -- surface those separately in the UI).
    """
    if label_column is None:
        label_column = df.columns[0]

    merged = df.merge(mapping, left_on=label_column, right_on="raw_label", how="left")
    matched = merged[merged["canonical_field"].notna()].copy()
    matched = matched.drop(columns=[label_column, "raw_label", "confidence", "match_type"])
    matched = matched.rename(columns={"canonical_field": "line_item"})

    # reorder so line_item is first
    cols = ["line_item"] + [c for c in matched.columns if c != "line_item"]
    return matched[cols]


if __name__ == "__main__":
    import sys as _sys
    from extract import extract_file

    if len(_sys.argv) < 2:
        print("Usage: python transform.py <path_to_file>")
    else:
        df = extract_file(_sys.argv[1])
        mapping = map_raw_dataframe(df)

        print("\n--- Field Mapping Results ---")
        print(mapping.to_string(index=False))

        print("\n--- Summary ---")
        print(mapping["match_type"].value_counts().to_string())

        unmatched = mapping[mapping["match_type"] == "unmatched"]
        if not unmatched.empty:
            print(f"\n{len(unmatched)} label(s) need manual mapping:")
            print(unmatched["raw_label"].tolist())