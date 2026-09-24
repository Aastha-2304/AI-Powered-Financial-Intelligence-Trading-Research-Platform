"""
Extract module for AI Financial Intelligence Platform
Reads an uploaded financial statement file (CSV or Excel) into a raw DataFrame.
No cleaning or field-mapping happens here -- that's transform.py's job.
"""
import sys
from pathlib import Path
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")


def extract_file(file_path) -> pd.DataFrame:
    """
    Read a raw uploaded file into a DataFrame, exactly as-is.
    Accepts .csv, .xlsx, .xls. Works with both a file path and a
    Streamlit UploadedFile object (has a .name attribute).
    """
    file_path = Path(file_path) if isinstance(file_path, (str, Path)) else file_path
    name = getattr(file_path, "name", str(file_path))
    suffix = Path(name).suffix.lower()

    if suffix == ".csv":
        df = pd.read_csv(file_path)
    elif suffix in (".xlsx", ".xls"):
        df = pd.read_excel(file_path)
    else:
        raise ValueError(f"Unsupported file type: {suffix}. Please upload .csv or .xlsx")

    print(f"Extracted raw file: {name} -> {df.shape[0]} rows, {df.shape[1]} columns")
    return df


def inspect_raw_structure(df: pd.DataFrame) -> dict:
    """
    Quick diagnostic: shows what we're working with before any cleaning.
    Helps decide in transform.py whether line items are in rows or columns.
    """
    return {
        "shape": df.shape,
        "columns": list(df.columns),
        "first_column_values": df.iloc[:, 0].dropna().astype(str).tolist()[:15],
        "dtypes": df.dtypes.astype(str).to_dict(),
    }


if __name__ == "__main__":
    import sys as _sys
    if len(_sys.argv) < 2:
        print("Usage: python extract.py <path_to_file>")
    else:
        df = extract_file(_sys.argv[1])
        print("\n--- Raw structure ---")
        info = inspect_raw_structure(df)
        for k, v in info.items():
            print(f"{k}: {v}")