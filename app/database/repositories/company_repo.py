"""
Company repository: parameterized CRUD for companies.
"""
from typing import Optional, List
import duckdb
from app.schemas.financial import Company


class CompanyRepository:
    """Repository handling company entity queries."""
    def __init__(self, conn: duckdb.DuckDBPyConnection):
        self.conn = conn

    def create(self, company: Company) -> Company:
        self.conn.execute(
            """
            INSERT INTO companies (company_id, name, ticker, reporting_currency, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (company_id) DO UPDATE SET
                name = excluded.name,
                ticker = excluded.ticker,
                reporting_currency = excluded.reporting_currency
            """,
            [
                company.company_id,
                company.name,
                company.ticker,
                company.reporting_currency,
                company.created_at,
            ],
        )
        return company

    def get_by_id(self, company_id: str) -> Optional[Company]:
        res = self.conn.execute(
            """
            SELECT company_id, name, ticker, reporting_currency, created_at
            FROM companies
            WHERE company_id = ?
            """,
            [company_id],
        ).fetchone()
        if not res:
            return None
        return Company(
            company_id=res[0],
            name=res[1],
            ticker=res[2],
            reporting_currency=res[3],
            created_at=res[4],
        )

    def list_all(self) -> List[Company]:
        rows = self.conn.execute(
            """
            SELECT company_id, name, ticker, reporting_currency, created_at
            FROM companies
            ORDER BY name ASC
            """
        ).fetchall()
        return [
            Company(
                company_id=r[0],
                name=r[1],
                ticker=r[2],
                reporting_currency=r[3],
                created_at=r[4],
            )
            for r in rows
        ]
