"""
Financial facts repository: stores atomic financial observations with provenance.
Parameterized SQL guarantees no SQL injection.
"""
from typing import List, Optional, Dict, Any
import duckdb
from app.schemas.financial import FinancialFact


class FinancialFactRepository:
    def __init__(self, conn: duckdb.DuckDBPyConnection):
        self.conn = conn

    def insert_facts_batch(self, facts: List[FinancialFact]) -> None:
        """Batch inserts financial facts within active transaction."""
        for f in facts:
            self.conn.execute(
                """
                INSERT INTO financial_facts (
                    fact_id, dataset_id, dataset_version, statement_type, canonical_item,
                    period, period_type, original_label, original_value, original_unit,
                    original_currency, normalized_value, normalized_currency, scaling_factor,
                    source_file, source_sheet, source_row, mapping_method, mapping_confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (dataset_id, dataset_version, canonical_item, period) DO UPDATE SET
                    normalized_value = excluded.normalized_value,
                    original_value = excluded.original_value,
                    original_label = excluded.original_label,
                    mapping_method = excluded.mapping_method,
                    mapping_confidence = excluded.mapping_confidence
                """,
                [
                    f.fact_id,
                    f.dataset_id,
                    f.dataset_version,
                    f.statement_type,
                    f.canonical_item,
                    f.period,
                    f.period_type,
                    f.original_label,
                    f.original_value,
                    f.original_unit,
                    f.original_currency,
                    f.normalized_value,
                    f.normalized_currency,
                    f.scaling_factor,
                    f.source_file,
                    f.source_sheet,
                    f.source_row,
                    f.mapping_method,
                    f.mapping_confidence,
                ],
            )

    def get_fact(
        self,
        dataset_id: str,
        dataset_version: int,
        canonical_item: str,
        period: str,
    ) -> Optional[FinancialFact]:
        """Typed lookup for a specific fact."""
        res = self.conn.execute(
            """
            SELECT fact_id, dataset_id, dataset_version, statement_type, canonical_item,
                   period, period_type, original_label, original_value, original_unit,
                   original_currency, normalized_value, normalized_currency, scaling_factor,
                   source_file, source_sheet, source_row, mapping_method, mapping_confidence
            FROM financial_facts
            WHERE dataset_id = ? AND dataset_version = ?
              AND canonical_item = ? AND period = ?
            """,
            [dataset_id, dataset_version, canonical_item, period],
        ).fetchone()
        if not res:
            return None
        return FinancialFact(
            fact_id=res[0],
            dataset_id=res[1],
            dataset_version=res[2],
            statement_type=res[3],
            canonical_item=res[4],
            period=res[5],
            period_type=res[6],
            original_label=res[7],
            original_value=res[8],
            original_unit=res[9],
            original_currency=res[10],
            normalized_value=res[11],
            normalized_currency=res[12],
            scaling_factor=res[13],
            source_file=res[14],
            source_sheet=res[15],
            source_row=res[16],
            mapping_method=res[17],
            mapping_confidence=res[18],
        )

    def get_statement_facts(
        self,
        dataset_id: str,
        dataset_version: int,
        statement_type: Optional[str] = None,
    ) -> List[FinancialFact]:
        """Returns all facts for a dataset version, optionally filtered by statement type."""
        query = """
            SELECT fact_id, dataset_id, dataset_version, statement_type, canonical_item,
                   period, period_type, original_label, original_value, original_unit,
                   original_currency, normalized_value, normalized_currency, scaling_factor,
                   source_file, source_sheet, source_row, mapping_method, mapping_confidence
            FROM financial_facts
            WHERE dataset_id = ? AND dataset_version = ?
        """
        params: List[Any] = [dataset_id, dataset_version]
        if statement_type:
            query += " AND statement_type = ?"
            params.append(statement_type)
        query += " ORDER BY period ASC, canonical_item ASC"

        rows = self.conn.execute(query, params).fetchall()
        return [
            FinancialFact(
                fact_id=r[0],
                dataset_id=r[1],
                dataset_version=r[2],
                statement_type=r[3],
                canonical_item=r[4],
                period=r[5],
                period_type=r[6],
                original_label=r[7],
                original_value=r[8],
                original_unit=r[9],
                original_currency=r[10],
                normalized_value=r[11],
                normalized_currency=r[12],
                scaling_factor=r[13],
                source_file=r[14],
                source_sheet=r[15],
                source_row=r[16],
                mapping_method=r[17],
                mapping_confidence=r[18],
            )
            for r in rows
        ]
