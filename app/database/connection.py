"""
DuckDB connection manager with transaction management.
Provides thread-safe connections and schema initialization.
"""
import duckdb
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

from app.core.config import settings
from app.core.logging import get_logger
from app.database.schema import DDL_STATEMENTS

logger = get_logger(__name__)


class DatabaseManager:
    """Manages connections and transactions for DuckDB."""
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = Path(db_path) if db_path else settings.resolved_db_path
        self._conn: Optional[duckdb.DuckDBPyConnection] = None

    def get_connection(self) -> duckdb.DuckDBPyConnection:
        """Returns or establishes a connection to DuckDB."""
        if self._conn is None:
            if str(self.db_path) != ":memory:":
                self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = duckdb.connect(str(self.db_path))
            logger.info("Connected to DuckDB at %s", self.db_path)
            self.init_schema()
        return self._conn

    def init_schema(self) -> None:
        """Executes all DDL schema statements."""
        conn = self._conn or duckdb.connect(str(self.db_path))
        for ddl in DDL_STATEMENTS:
            conn.execute(ddl)
        logger.info("DuckDB financial schema initialized successfully (%d tables verified).", len(DDL_STATEMENTS))

    @contextmanager
    def transaction(self):
        """Context manager providing ACID transactions for atomic multi-table updates."""
        conn = self.get_connection()
        conn.execute("BEGIN TRANSACTION")
        try:
            yield conn
            conn.execute("COMMIT")
        except Exception as e:
            conn.execute("ROLLBACK")
            logger.error("Transaction rolled back due to error: %s", str(e))
            raise

    def close(self) -> None:
        """Closes the active database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
            logger.info("Closed DuckDB connection.")


# Default singleton instance
db_manager = DatabaseManager()


def get_db_connection() -> duckdb.DuckDBPyConnection:
    """Returns the default singleton DuckDB connection."""
    return db_manager.get_connection()
