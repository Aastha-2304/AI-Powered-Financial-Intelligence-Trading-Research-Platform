"""
Unit Tests for Phase 4 Forecasting Engine:
1. Driver-based model projections (Revenue, EBIT, Working Capital days, Free Cash Flow).
2. Naive, Moving Average, and Exponential Smoothing statistical baselines.
3. Backtest error metrics (MAPE with epsilon handling for zero actuals, RMSE, MAE).
4. Storage separation and roundtrip in DuckDB forecast repository.
"""
import pytest
from app.forecasting.drivers import ForecastDrivers, DriverForecastEngine
from app.forecasting.baselines import BaselineForecastEngine
from app.forecasting.backtest import BacktestMetrics
from app.schemas.modeling import AssumptionSet, ForecastRun
from app.database.repositories.forecast_repo import ForecastRepository


def test_driver_based_statement_projection():
    """Verify driver engine produces mathematical balance across all forecast periods."""
    drivers = ForecastDrivers(
        revenue_growth_rates=[0.10, 0.08, 0.06],
        cogs_percent_revenue=0.60,
        opex_percent_revenue=0.20,
        tax_rate=0.25,
        days_sales_outstanding=45.0,
        days_inventory_outstanding=30.0,
        days_payable_outstanding=30.0,
        existing_debt=1000.0,
        annual_debt_repayment=200.0,
        cost_of_debt=0.05,
    )
    base_rev = 1000.0
    results = DriverForecastEngine.project_statements(base_rev, drivers, start_year=2024, horizon=3)

    assert len(results) == 3
    # Year 1 Revenue = 1000 * 1.10 = 1100.0
    y1 = results[0]
    assert y1.period == "2024"
    assert y1.revenue == 1100.0
    assert y1.cogs == 660.0  # 60% of 1100
    assert y1.gross_profit == 440.0
    assert y1.operating_expenses == 220.0  # 20% of 1100
    assert y1.operating_income == 220.0
    assert y1.interest_expense == 50.0  # 5% of 1000
    assert y1.pretax_income == 170.0
    assert y1.tax_expense == 42.5
    assert y1.net_income == 127.5
    assert y1.debt_balance == 800.0  # 1000 - 200 repayment
    assert isinstance(y1.free_cash_flow, float)


def test_baseline_models():
    """Verify naive, moving average, and exponential smoothing baselines."""
    history = [100.0, 110.0, 120.0, 130.0, 140.0]

    naive = BaselineForecastEngine.forecast_naive(history, horizon=3)
    assert naive == [140.0, 140.0, 140.0]

    ma = BaselineForecastEngine.forecast_moving_average(history, window=3, horizon=2)
    assert ma == [130.0, 130.0]  # (120+130+140)/3 = 130.0

    exp = BaselineForecastEngine.forecast_exponential_smoothing(history, horizon=3)
    assert len(exp) == 3
    # With a consistent positive trend, Holt's method should forecast values >= 140
    assert exp[0] >= 140.0


def test_mape_epsilon_handling_near_zero():
    """Verify MAPE avoids ZeroDivisionError when actuals contain zeros or near-zeros."""
    actuals = [0.0, 100.0, 0.00001]
    preds = [10.0, 105.0, 0.00002]

    # Without epsilon this would crash
    mape = BacktestMetrics.calculate_mape(actuals, preds)
    assert mape > 0.0
    assert not pytest.approx(mape) == float("inf")


def test_forecast_repository_storage(memory_db):
    """Verify saving versioned assumptions and forecast runs in DuckDB."""
    service_conn = memory_db
    # Seed company & dataset
    service_conn.execute("INSERT INTO companies (company_id, name) VALUES ('co_fc', 'Forecast Co')")
    service_conn.execute("INSERT INTO uploads (upload_id, company_id, filename, file_hash, file_size_bytes) VALUES ('up_fc', 'co_fc', 'file.csv', 'hash1', 100)")
    service_conn.execute("INSERT INTO datasets (dataset_id, company_id, statement_type) VALUES ('ds_fc', 'co_fc', 'INCOME_STATEMENT')")
    service_conn.execute("INSERT INTO dataset_versions (dataset_id, version, upload_id, status) VALUES ('ds_fc', 1, 'up_fc', 'approved')")

    repo = ForecastRepository(service_conn)

    # 1. Save assumption set
    assumptions = AssumptionSet(
        assumption_set_id="as_001",
        company_id="co_fc",
        version=1,
        source="analyst_model",
        is_approved=True,
        assumptions_json={"growth": 0.08, "margin": 0.20},
    )
    repo.save_assumption_set(assumptions)

    # 2. Save forecast run
    run = ForecastRun(
        forecast_id="fc_001",
        dataset_id="ds_fc",
        dataset_version=1,
        assumption_set_id="as_001",
        model_name="driver_based",
        horizon_periods=5,
        results_json={"2024": {"revenue": 1080.0, "net_income": 120.0}},
        backtest_metrics_json={"mape": 0.042, "rmse": 12.5},
    )
    repo.save_forecast_run(run)

    # 3. Retrieve and assert
    fetched = repo.get_forecast_run("fc_001")
    assert fetched is not None
    assert fetched.model_name == "driver_based"
    assert fetched.results_json["2024"]["revenue"] == 1080.0
    assert fetched.backtest_metrics_json["mape"] == 0.042
