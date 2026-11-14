"""
Typed, allowlisted query tools for the Grounded AI Analyst.
Crucial Security & Soundness Rule:
- NO unrestricted LLM text-to-SQL is permitted.
- The LLM never touches raw SQL.
- All data retrieval passes through typed Pydantic queries executed via parameterized DuckDB SQL.
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import duckdb

from app.core.security import AuthContext
from app.schemas.financial import FinancialFact


class EvidenceItem(BaseModel):
    """Structured atomic evidence supporting a factual financial response."""
    canonical_item: str
    period: str
    normalized_value: float
    currency: str
    statement_type: str
    original_label: str
    original_value: float
    original_unit: str
    source_file: str
    source_row: Optional[int] = None
    dataset_id: str
    dataset_version: int
    provenance_reference: str


class EvidenceBundle(BaseModel):
    """Collection of verifiable facts and model results retrieved for a user prompt."""
    query_intent: str
    company_id: str
    dataset_id: Optional[str] = None
    dataset_version: Optional[int] = None
    items: List[EvidenceItem] = []
    derived_metrics: Dict[str, Any] = {}
    abstention_reason: Optional[str] = None
    is_sufficient: bool = True


class TypedFinancialQueryTools:
    """Allowlisted typed query execution over DuckDB warehouse."""

    def __init__(self, conn: duckdb.DuckDBPyConnection):
        self.conn = conn

    def get_line_item(
        self,
        company_id: str,
        canonical_item: str,
        period: str,
        dataset_version: Optional[int] = None,
    ) -> Optional[EvidenceItem]:
        """Typed factual query for a single line item in a specific period."""
        version_clause = "AND f.dataset_version = ?" if dataset_version else "AND v.is_active = TRUE"
        params: List[Any] = [company_id, canonical_item, period]
        if dataset_version:
            params.append(dataset_version)

        query = f"""
            SELECT f.canonical_item, f.period, f.normalized_value, f.normalized_currency,
                   f.statement_type, f.original_label, f.original_value, f.original_unit,
                   f.source_file, f.source_row, f.dataset_id, f.dataset_version
            FROM financial_facts f
            JOIN dataset_versions v ON f.dataset_id = v.dataset_id AND f.dataset_version = v.version
            JOIN datasets d ON f.dataset_id = d.dataset_id
            WHERE d.company_id = ?
              AND f.canonical_item = ?
              AND f.period = ?
              {version_clause}
            ORDER BY f.dataset_version DESC
            LIMIT 1
        """
        row = self.conn.execute(query, params).fetchone()
        if not row:
            return None

        prov_ref = f"{row[8]} (row {row[9] or 'N/A'}, {row[4]}, {row[1]})"
        return EvidenceItem(
            canonical_item=row[0],
            period=row[1],
            normalized_value=row[2],
            currency=row[3],
            statement_type=row[4],
            original_label=row[5],
            original_value=row[6],
            original_unit=row[7],
            source_file=row[8],
            source_row=row[9],
            dataset_id=row[10],
            dataset_version=row[11],
            provenance_reference=prov_ref,
        )

    def get_line_item_history(
        self,
        company_id: str,
        canonical_item: str,
    ) -> List[EvidenceItem]:
        """Typed query for historical series of a line item across all active periods."""
        query = """
            SELECT f.canonical_item, f.period, f.normalized_value, f.normalized_currency,
                   f.statement_type, f.original_label, f.original_value, f.original_unit,
                   f.source_file, f.source_row, f.dataset_id, f.dataset_version
            FROM financial_facts f
            JOIN dataset_versions v ON f.dataset_id = v.dataset_id AND f.dataset_version = v.version
            JOIN datasets d ON f.dataset_id = d.dataset_id
            WHERE d.company_id = ?
              AND f.canonical_item = ?
              AND v.is_active = TRUE
            ORDER BY f.period ASC
        """
        rows = self.conn.execute(query, [company_id, canonical_item]).fetchall()
        return [
            EvidenceItem(
                canonical_item=r[0],
                period=r[1],
                normalized_value=r[2],
                currency=r[3],
                statement_type=r[4],
                original_label=r[5],
                original_value=r[6],
                original_unit=r[7],
                source_file=r[8],
                source_row=r[9],
                dataset_id=r[10],
                dataset_version=r[11],
                provenance_reference=f"{r[8]} (row {r[9] or 'N/A'}, {r[4]}, {r[1]})",
            )
            for r in rows
        ]

    def get_statement_period(
        self,
        company_id: str,
        statement_type: str,
        period: str,
    ) -> List[EvidenceItem]:
        """Typed query for all items of a statement in a period."""
        query = """
            SELECT f.canonical_item, f.period, f.normalized_value, f.normalized_currency,
                   f.statement_type, f.original_label, f.original_value, f.original_unit,
                   f.source_file, f.source_row, f.dataset_id, f.dataset_version
            FROM financial_facts f
            JOIN dataset_versions v ON f.dataset_id = v.dataset_id AND f.dataset_version = v.version
            JOIN datasets d ON f.dataset_id = d.dataset_id
            WHERE d.company_id = ?
              AND f.statement_type = ?
              AND f.period = ?
              AND v.is_active = TRUE
            ORDER BY f.canonical_item ASC
        """
        rows = self.conn.execute(query, [company_id, statement_type, period]).fetchall()
        return [
            EvidenceItem(
                canonical_item=r[0],
                period=r[1],
                normalized_value=r[2],
                currency=r[3],
                statement_type=r[4],
                original_label=r[5],
                original_value=r[6],
                original_unit=r[7],
                source_file=r[8],
                source_row=r[9],
                dataset_id=r[10],
                dataset_version=r[11],
                provenance_reference=f"{r[8]} (row {r[9] or 'N/A'}, {r[4]}, {r[1]})",
            )
            for r in rows
        ]

    def get_latest_valuation(self, company_id: str) -> Optional[Dict[str, Any]]:
        """Typed lookup for active company DCF valuation."""
        query = """
            SELECT vr.valuation_id, vr.dataset_id, vr.dataset_version, vr.wacc,
                   vr.terminal_growth_rate, vr.enterprise_value, vr.equity_value,
                   vr.implied_share_price, vr.sensitivity_grid_json, vr.scenarios_json
            FROM valuation_runs vr
            JOIN datasets d ON vr.dataset_id = d.dataset_id
            WHERE d.company_id = ?
            ORDER BY vr.created_at DESC LIMIT 1
        """
        row = self.conn.execute(query, [company_id]).fetchone()
        if not row:
            return None
        import json
        return {
            "valuation_id": row[0],
            "dataset_id": row[1],
            "dataset_version": row[2],
            "wacc": row[3],
            "terminal_growth_rate": row[4],
            "enterprise_value": row[5],
            "equity_value": row[6],
            "implied_share_price": row[7],
            "sensitivity_grid": json.loads(row[8]),
            "scenarios": json.loads(row[9]),
        }
