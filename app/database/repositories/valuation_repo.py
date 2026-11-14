"""
Valuation Repository: records valuation runs and scenario analyses in DuckDB.
Stores DCF results, sensitivity matrices, and scenarios referencing specific dataset versions.
"""
from typing import Optional
import json
import duckdb
from app.schemas.modeling import ValuationRun


class ValuationRepository:
    """Repository handling versioned DCF valuation and scenario outputs."""

    def __init__(self, conn: duckdb.DuckDBPyConnection):
        self.conn = conn

    def save_valuation_run(self, val: ValuationRun) -> ValuationRun:
        self.conn.execute(
            """
            INSERT INTO valuation_runs (
                valuation_id, dataset_id, dataset_version, forecast_id,
                assumption_set_id, wacc, terminal_growth_rate,
                enterprise_value, equity_value, implied_share_price,
                sensitivity_grid_json, scenarios_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (valuation_id) DO NOTHING
            """,
            [
                val.valuation_id,
                val.dataset_id,
                val.dataset_version,
                val.forecast_id,
                val.assumption_set_id,
                val.wacc,
                val.terminal_growth_rate,
                val.enterprise_value,
                val.equity_value,
                val.implied_share_price,
                json.dumps(val.sensitivity_grid_json),
                json.dumps(val.scenarios_json),
                val.created_at,
            ],
        )
        return val

    def get_valuation_run(self, valuation_id: str) -> Optional[ValuationRun]:
        res = self.conn.execute(
            """
            SELECT valuation_id, dataset_id, dataset_version, forecast_id,
                   assumption_set_id, wacc, terminal_growth_rate,
                   enterprise_value, equity_value, implied_share_price,
                   sensitivity_grid_json, scenarios_json, created_at
            FROM valuation_runs
            WHERE valuation_id = ?
            """,
            [valuation_id],
        ).fetchone()
        if not res:
            return None
        return ValuationRun(
            valuation_id=res[0],
            dataset_id=res[1],
            dataset_version=res[2],
            forecast_id=res[3],
            assumption_set_id=res[4],
            wacc=res[5],
            terminal_growth_rate=res[6],
            enterprise_value=res[7],
            equity_value=res[8],
            implied_share_price=res[9],
            sensitivity_grid_json=json.loads(res[10]),
            scenarios_json=json.loads(res[11]),
            created_at=res[12],
        )
