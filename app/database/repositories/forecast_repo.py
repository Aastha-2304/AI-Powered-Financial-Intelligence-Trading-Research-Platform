"""
Forecast Repository: records assumption sets and forecast runs in DuckDB.
Stores drivers and projections with clear separation from historical facts.
"""
from typing import List, Optional
import json
import duckdb
from app.schemas.modeling import AssumptionSet, ForecastRun


class ForecastRepository:
    """Repository handling versioned forecast assumptions and outputs."""

    def __init__(self, conn: duckdb.DuckDBPyConnection):
        self.conn = conn

    def save_assumption_set(self, assumptions: AssumptionSet) -> AssumptionSet:
        self.conn.execute(
            """
            INSERT INTO assumption_sets (
                assumption_set_id, company_id, version, source,
                is_approved, assumptions_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (assumption_set_id) DO NOTHING
            """,
            [
                assumptions.assumption_set_id,
                assumptions.company_id,
                assumptions.version,
                assumptions.source,
                assumptions.is_approved,
                json.dumps(assumptions.assumptions_json),
                assumptions.created_at,
            ],
        )
        return assumptions

    def save_forecast_run(self, run: ForecastRun) -> ForecastRun:
        self.conn.execute(
            """
            INSERT INTO forecast_runs (
                forecast_id, dataset_id, dataset_version, assumption_set_id,
                model_name, horizon_periods, results_json,
                backtest_metrics_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (forecast_id) DO NOTHING
            """,
            [
                run.forecast_id,
                run.dataset_id,
                run.dataset_version,
                run.assumption_set_id,
                run.model_name,
                run.horizon_periods,
                json.dumps(run.results_json),
                json.dumps(run.backtest_metrics_json or {}),
                run.created_at,
            ],
        )
        return run

    def get_forecast_run(self, forecast_id: str) -> Optional[ForecastRun]:
        res = self.conn.execute(
            """
            SELECT forecast_id, dataset_id, dataset_version, assumption_set_id,
                   model_name, horizon_periods, results_json,
                   backtest_metrics_json, created_at
            FROM forecast_runs
            WHERE forecast_id = ?
            """,
            [forecast_id],
        ).fetchone()
        if not res:
            return None
        return ForecastRun(
            forecast_id=res[0],
            dataset_id=res[1],
            dataset_version=res[2],
            assumption_set_id=res[3],
            model_name=res[4],
            horizon_periods=res[5],
            results_json=json.loads(res[6]),
            backtest_metrics_json=json.loads(res[7]) if res[7] else None,
            created_at=res[8],
        )
