"""
Load module for AI Financial Intelligence Platform
Stores canonically-mapped, validated financial data into DuckDB.
Each upload is appended, building a history of filings/periods.
"""
import sys
import uuid
from datetime import datetime
from pathlib import Path
import duckdb
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

sys.path.append(str(Path(__file__).resolve().parent.parent))
from config import DB_PATH


def get_connection() -> duckdb.DuckDBPyConnection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(DB_PATH))


def ensure_schema(conn: duckdb.DuckDBPyConnection):
    """Create tables if they don't exist yet. Never drops existing data."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS uploads (
            upload_id VARCHAR PRIMARY KEY,
            company_name VARCHAR,
            source_filename VARCHAR,
            uploaded_at TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS financial_data (
            upload_id VARCHAR,
            company_name VARCHAR,
            line_item VARCHAR,
            period VARCHAR,
            value DOUBLE
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS validation_issues (
            upload_id VARCHAR,
            company_name VARCHAR,
            check_name VARCHAR,
            line_item VARCHAR,
            period VARCHAR,
            severity VARCHAR,
            message VARCHAR
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS quality_scores (
            upload_id VARCHAR PRIMARY KEY,
            company_name VARCHAR,
            score INTEGER,
            total_issues INTEGER,
            high_severity INTEGER,
            medium_severity INTEGER,
            low_severity INTEGER,
            scored_at TIMESTAMP
        )
    """)


def wide_to_long(clean_df: pd.DataFrame) -> pd.DataFrame:
    """Convert wide (line_item, 2022, 2023, 2024) to long (line_item, period, value)."""
    period_cols = [c for c in clean_df.columns if c != "line_item"]
    long_df = clean_df.melt(id_vars="line_item", value_vars=period_cols,
                             var_name="period", value_name="value")
    return long_df.dropna(subset=["value"])


def load_upload(conn, company_name: str, source_filename: str,
                 clean_df: pd.DataFrame, issues: pd.DataFrame, score: dict) -> str:
    """
    Stores one full upload: the upload record, its financial data (long format),
    its validation issues, and its quality score. Returns the generated upload_id.
    """
    upload_id = str(uuid.uuid4())
    now = datetime.now()

    conn.execute(
        "INSERT INTO uploads VALUES (?, ?, ?, ?)",
        [upload_id, company_name, source_filename, now],
    )

    long_df = wide_to_long(clean_df)
    long_df.insert(0, "upload_id", upload_id)
    long_df.insert(1, "company_name", company_name)
    conn.register("temp_financial_data", long_df)
    conn.execute("INSERT INTO financial_data SELECT * FROM temp_financial_data")
    conn.unregister("temp_financial_data")

    if not issues.empty:
        issues_out = issues.rename(columns={"check": "check_name"}).copy()
        issues_out.insert(0, "upload_id", upload_id)
        issues_out.insert(1, "company_name", company_name)
        issues_out = issues_out[["upload_id", "company_name", "check_name",
                                  "line_item", "period", "severity", "message"]]
        conn.register("temp_issues", issues_out)
        conn.execute("INSERT INTO validation_issues SELECT * FROM temp_issues")
        conn.unregister("temp_issues")

    conn.execute(
        "INSERT INTO quality_scores VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [upload_id, company_name, score["score"], score["total_issues"],
         int(score["high_severity"]), int(score["medium_severity"]), int(score["low_severity"]), now],
    )

    print(f"Loaded upload {upload_id} for '{company_name}': "
          f"{len(long_df)} data points, {len(issues)} issues, score={score['score']}")
    return upload_id


if __name__ == "__main__":
    import sys as _sys
    from extract import extract_file
    from transform import map_raw_dataframe, apply_mapping
    from validate import run_all_validations, data_quality_score

    if len(_sys.argv) < 3:
        print("Usage: python load.py <path_to_file> <company_name>")
    else:
        file_path = _sys.argv[1]
        company_name = _sys.argv[2]

        raw_df = extract_file(file_path)
        mapping = map_raw_dataframe(raw_df)
        clean_df = apply_mapping(raw_df, mapping)
        issues = run_all_validations(clean_df)
        score = data_quality_score(clean_df, issues)

        conn = get_connection()
        try:
            ensure_schema(conn)
            upload_id = load_upload(conn, company_name, Path(file_path).name, clean_df, issues, score)

            print("\n--- Verification ---")
            print(conn.execute("SELECT COUNT(*) FROM uploads").fetchdf())
            print(conn.execute("SELECT COUNT(*) FROM financial_data").fetchdf())
            print(conn.execute(f"""
                SELECT line_item, period, value FROM financial_data
                WHERE upload_id = '{upload_id}' ORDER BY line_item, period
            """).fetchdf().to_string(index=False))
        finally:
            conn.close()