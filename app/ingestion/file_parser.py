"""
Upload verification and tabular file parser.
Provides security checks: extension, size limit, path traversal defense,
SHA256 duplicate calculation, and tabular extraction for CSV and Excel.
"""
import hashlib
import os
from pathlib import Path
from typing import Tuple, List, Dict, Any, Optional
import pandas as pd

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB limit
ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}


class FileParserError(Exception):
    """Domain error raised on file verification or parsing failure."""
    pass


class FileParser:
    """Secure parser for financial statement spreadsheets and CSV files."""

    @staticmethod
    def compute_sha256(content: bytes) -> str:
        """Computes SHA-256 hash of file bytes for idempotent deduplication."""
        return hashlib.sha256(content).hexdigest()

    @staticmethod
    def validate_file(filename: str, content: bytes) -> str:
        """
        Validates file extension, size limit, and prevents directory traversal attacks.
        Returns the safe sanitized basename.
        """
        if not filename:
            raise FileParserError("Filename cannot be empty.")

        # Defense against path traversal
        clean_basename = os.path.basename(filename).strip()
        if not clean_basename or ".." in clean_basename:
            raise FileParserError("Invalid or malicious filename detected.")

        ext = Path(clean_basename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise FileParserError(
                f"Unsupported file format '{ext}'. Allowed formats: {', '.join(ALLOWED_EXTENSIONS)}"
            )

        if len(content) == 0:
            raise FileParserError("Uploaded file is empty (0 bytes).")

        if len(content) > MAX_FILE_SIZE_BYTES:
            raise FileParserError(
                f"File size exceeds limit of {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB."
            )

        return clean_basename

    @classmethod
    def parse_tabular_data(
        cls,
        filename: str,
        content: bytes,
        sheet_name: Optional[str] = None,
    ) -> List[Tuple[str, pd.DataFrame]]:
        """
        Parses CSV or Excel bytes into a list of (sheet_name, DataFrame) tuples.
        Headers are preserved as raw strings.
        """
        safe_filename = cls.validate_file(filename, content)
        ext = Path(safe_filename).suffix.lower()

        try:
            import io
            stream = io.BytesIO(content)

            if ext == ".csv":
                # Handle possible encodings
                try:
                    df = pd.read_csv(stream, encoding="utf-8")
                except UnicodeDecodeError:
                    stream.seek(0)
                    df = pd.read_csv(stream, encoding="latin1")
                return [("CSV", df)]

            elif ext in {".xlsx", ".xls"}:
                excel_file = pd.ExcelFile(stream)
                sheets_to_read = [sheet_name] if sheet_name else excel_file.sheet_names
                results = []
                for s in sheets_to_read:
                    df = pd.read_excel(excel_file, sheet_name=s)
                    results.append((s, df))
                return results

            else:
                raise FileParserError(f"Unhandled file extension: {ext}")

        except Exception as e:
            if isinstance(e, FileParserError):
                raise
            logger.error("Failed to parse tabular file '%s': %s", safe_filename, str(e))
            raise FileParserError(f"Failed to read spreadsheet: {str(e)}") from e
