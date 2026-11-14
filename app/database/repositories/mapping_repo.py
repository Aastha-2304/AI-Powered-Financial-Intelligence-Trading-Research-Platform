"""
Mapping, Review, and Alias repository.
Handles alias matching dictionary and human reviewer decision logging.
"""
from typing import List, Optional
import duckdb
from app.schemas.financial import LineItemAlias
from app.schemas.workflow import MappingReviewDecision


class MappingRepository:
    def __init__(self, conn: duckdb.DuckDBPyConnection):
        self.conn = conn

    def get_aliases_by_statement(self, statement_type: str) -> List[LineItemAlias]:
        """Fetches active aliases for statement classification."""
        rows = self.conn.execute(
            """
            SELECT alias_id, alias, canonical_item, statement_type, provenance, is_approved
            FROM line_item_aliases
            WHERE statement_type = ? AND is_approved = TRUE
            """,
            [statement_type],
        ).fetchall()
        return [
            LineItemAlias(
                alias_id=r[0],
                alias=r[1],
                canonical_item=r[2],
                statement_type=r[3],
                provenance=r[4],
                is_approved=r[5],
            )
            for r in rows
        ]

    def insert_alias(self, alias: LineItemAlias) -> None:
        self.conn.execute(
            """
            INSERT INTO line_item_aliases (alias_id, alias, canonical_item, statement_type, provenance, is_approved)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (alias) DO NOTHING
            """,
            [
                alias.alias_id,
                alias.alias,
                alias.canonical_item,
                alias.statement_type,
                alias.provenance,
                alias.is_approved,
            ],
        )

    def record_review_decision(self, decision: MappingReviewDecision) -> None:
        """Records a human reviewer's mapping approval/correction/rejection."""
        self.conn.execute(
            """
            INSERT INTO mapping_reviews (
                review_id, upload_id, raw_label, canonical_item, statement_type,
                decision, reviewer_id, reason, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (review_id) DO UPDATE SET
                decision = excluded.decision,
                canonical_item = excluded.canonical_item,
                reason = excluded.reason,
                timestamp = excluded.timestamp
            """,
            [
                decision.review_id,
                decision.upload_id,
                decision.raw_label,
                decision.canonical_item,
                decision.statement_type,
                decision.decision,
                decision.reviewer_id,
                decision.reason,
                decision.timestamp,
            ],
        )

    def get_review_decisions(self, upload_id: str) -> List[MappingReviewDecision]:
        rows = self.conn.execute(
            """
            SELECT review_id, upload_id, raw_label, canonical_item, statement_type,
                   decision, reviewer_id, reason, timestamp
            FROM mapping_reviews
            WHERE upload_id = ?
            ORDER BY timestamp ASC
            """,
            [upload_id],
        ).fetchall()
        return [
            MappingReviewDecision(
                review_id=r[0],
                upload_id=r[1],
                raw_label=r[2],
                canonical_item=r[3],
                statement_type=r[4],
                decision=r[5],
                reviewer_id=r[6],
                reason=r[7],
                timestamp=r[8],
            )
            for r in rows
        ]
