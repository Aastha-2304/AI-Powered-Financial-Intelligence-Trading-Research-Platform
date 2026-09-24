"""
Data Quality / Lineage module for AI Financial Intelligence Platform.
Persists the fuzzy-match field mapping (previously shown once during
upload and discarded) so it can be reviewed later, and provides summary
queries combining mapping confidence + validation issues + quality score
into one "data health" view.
"""


def ensure_mapping_schema(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS field_mappings (
            upload_id VARCHAR,
            raw_label VARCHAR,
            canonical_field VARCHAR,
            confidence DOUBLE,
            match_type VARCHAR
        )
    """)


def save_field_mapping(conn, upload_id: str, mapping_df):
    """Call this right after load_upload() succeeds, passing the same
    `mapping` dataframe already built during the upload flow. Columns
    expected: raw_label, canonical_field, confidence, match_type."""
    ensure_mapping_schema(conn)
    conn.execute("DELETE FROM field_mappings WHERE upload_id = ?", [upload_id])
    for _, row in mapping_df.iterrows():
        conn.execute("""
            INSERT INTO field_mappings (upload_id, raw_label, canonical_field, confidence, match_type)
            VALUES (?, ?, ?, ?, ?)
        """, [upload_id, row.get("raw_label"), row.get("canonical_field"),
              row.get("confidence"), row.get("match_type")])


def get_field_mapping(conn, upload_id: str):
    return conn.execute("""
        SELECT raw_label, canonical_field, confidence, match_type
        FROM field_mappings WHERE upload_id = ?
        ORDER BY CASE match_type
            WHEN 'exact' THEN 1 WHEN 'fuzzy_auto' THEN 2
            WHEN 'fuzzy_suggest' THEN 3 ELSE 4 END, confidence DESC
    """, [upload_id]).fetchdf()


def get_mapping_summary(conn, upload_id: str) -> dict:
    df = get_field_mapping(conn, upload_id)
    if df.empty:
        return {"exact": 0, "fuzzy_auto": 0, "fuzzy_suggest": 0, "unmatched": 0, "avg_confidence": None}
    counts = df["match_type"].value_counts().to_dict()
    matched = df[df["match_type"] != "unmatched"]
    avg_conf = matched["confidence"].mean() if not matched.empty else None
    return {
        "exact": counts.get("exact", 0),
        "fuzzy_auto": counts.get("fuzzy_auto", 0),
        "fuzzy_suggest": counts.get("fuzzy_suggest", 0),
        "unmatched": counts.get("unmatched", 0),
        "avg_confidence": avg_conf,
    }


def get_data_health_across_companies(conn):
    """One row per upload: quality score + mapping match-rate, for a
    cross-company health overview."""
    return conn.execute("""
        SELECT
            u.upload_id, u.company_name, u.source_filename, u.uploaded_at,
            q.score AS quality_score, q.total_issues, q.high_severity,
            (SELECT COUNT(*) FROM field_mappings fm WHERE fm.upload_id = u.upload_id
             AND fm.match_type != 'unmatched') AS fields_matched,
            (SELECT COUNT(*) FROM field_mappings fm WHERE fm.upload_id = u.upload_id) AS fields_total
        FROM uploads u
        LEFT JOIN quality_scores q ON q.upload_id = u.upload_id
        ORDER BY u.uploaded_at DESC
    """).fetchdf()