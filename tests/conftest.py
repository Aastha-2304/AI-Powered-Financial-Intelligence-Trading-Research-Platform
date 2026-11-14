"""
Pytest configuration and shared fixtures for in-memory DuckDB testing.
"""
import sys
from pathlib import Path
import pytest
import duckdb

# Ensure app package is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.database.connection import DatabaseManager
from app.database.schema import DDL_STATEMENTS
from app.database.repositories import (
    CompanyRepository,
    UploadRepository,
    DatasetRepository,
    FinancialFactRepository,
    MappingRepository,
    AuditRepository,
)


@pytest.fixture
def memory_db():
    """Provides a fresh in-memory DuckDB instance with all tables created."""
    conn = duckdb.connect(":memory:")
    for ddl in DDL_STATEMENTS:
        conn.execute(ddl)
    yield conn
    conn.close()


@pytest.fixture
def repos(memory_db):
    """Provides initialized repository instances over the in-memory database."""
    return {
        "company": CompanyRepository(memory_db),
        "upload": UploadRepository(memory_db),
        "dataset": DatasetRepository(memory_db),
        "fact": FinancialFactRepository(memory_db),
        "mapping": MappingRepository(memory_db),
        "audit": AuditRepository(memory_db),
        "conn": memory_db,
    }
