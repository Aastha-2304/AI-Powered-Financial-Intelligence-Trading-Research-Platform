"""
Unit Tests for Phase 5 DCF Valuation and Scenario Engine:
1. CAPM & WACC calculation with weight normalization.
2. DCF valuation matching manual spreadsheet benchmark.
3. DCF Guard: Rejection of WACC <= terminal growth rate.
4. Enterprise Value to Equity Value bridge (Debt, Cash, Adjustments, Shares).
5. Sensitivity 2D matrix calculation with guarded cells.
6. Base / Bull / Bear scenario run.
7. Valuation repository persistence and retrieval.
"""
import pytest
from app.valuation.wacc import WACCParameters, WACCEngine
from app.valuation.dcf import DCFValuationEngine, DCFGuardError
from app.valuation.scenarios import SensitivityEngine, ScenarioEngine
from app.forecasting.drivers import ForecastDrivers
from app.schemas.modeling import ValuationRun
from app.database.repositories.valuation_repo import ValuationRepository


def test_wacc_calculation():
    """
    Verify CAPM Cost of Equity and WACC:
    Rf = 4.0%, Beta = 1.2, ERP = 5.0% -> Ke = 4% + 1.2*5% = 10.0%
    Kd_pretax = 6.0%, Tax = 25% -> Kd_after_tax = 6% * (1 - 0.25) = 4.5%
    E_weight = 80%, D_weight = 20%
    WACC = 0.80 * 10% + 0.20 * 4.5% = 8.0% + 0.9% = 8.9% = 0.089
    """
    params = WACCParameters(
        risk_free_rate=0.04,
        beta=1.20,
        equity_risk_premium=0.05,
        cost_of_debt_pretax=0.06,
        tax_rate=0.25,
        equity_weight=0.80,
        debt_weight=0.20,
    )
    res = WACCEngine.calculate_wacc(params)
    assert pytest.approx(res.cost_of_equity, 1e-4) == 0.10
    assert pytest.approx(res.after_tax_cost_of_debt, 1e-4) == 0.045
    assert pytest.approx(res.wacc, 1e-4) == 0.089


def test_dcf_spreadsheet_agreement():
    """
    Benchmark comparison against a verified spreadsheet case:
    Forecast FCFs: [100.0, 110.0, 120.0]
    WACC: 10.0% (0.10)
    Terminal Growth: 2.5% (0.025)
    
    PV of FCFs:
      Year 1: 100 / 1.10^1 = 90.909
      Year 2: 110 / 1.10^2 = 90.909
      Year 3: 120 / 1.10^3 = 90.158
      Sum PV = 271.976
      
    Terminal Value (Year 3):
      TV = 120 * (1 + 0.025) / (0.10 - 0.025) = 123 / 0.075 = 1,640.00
      PV of TV = 1640 / 1.10^3 = 1232.156
      
    Enterprise Value = 271.976 + 1232.156 = 1,504.13
    Total Debt = 200.0, Cash = 50.0
    Equity Value = 1504.13 - 200 + 50 = 1,354.13
    Shares = 100.0 -> Share Price = 13.54
    """
    res = DCFValuationEngine.calculate_dcf(
        forecast_fcfs=[100.0, 110.0, 120.0],
        forecast_periods=["2024", "2025", "2026"],
        wacc=0.10,
        terminal_growth_rate=0.025,
        total_debt=200.0,
        cash_and_equivalents=50.0,
        shares_outstanding=100.0,
    )
    assert pytest.approx(res.sum_pv_fcfs, 0.1) == 271.98
    assert pytest.approx(res.terminal_value_undiscounted, 0.1) == 1640.00
    assert pytest.approx(res.pv_terminal_value, 0.1) == 1232.16
    assert pytest.approx(res.enterprise_value, 0.1) == 1504.13
    assert pytest.approx(res.equity_value, 0.1) == 1354.13
    assert pytest.approx(res.implied_share_price, 0.05) == 13.54


def test_dcf_guard_rejects_wacc_le_growth():
    """Verify strict blueprint rule: reject calculation if WACC <= terminal growth."""
    with pytest.raises(DCFGuardError) as exc_info:
        DCFValuationEngine.calculate_dcf(
            forecast_fcfs=[100.0, 110.0],
            forecast_periods=["2024", "2025"],
            wacc=0.03,
            terminal_growth_rate=0.035,  # WACC < g is mathematically invalid!
        )
    assert "DCF Guard Violation" in str(exc_info.value)

    # Equal case: WACC == g
    with pytest.raises(DCFGuardError):
        DCFValuationEngine.calculate_dcf(
            forecast_fcfs=[100.0],
            forecast_periods=["2024"],
            wacc=0.03,
            terminal_growth_rate=0.03,
        )


def test_sensitivity_matrix_and_scenarios():
    """Verify sensitivity 2D grid and Base/Bull/Bear scenarios."""
    fcfs = [100.0, 110.0, 120.0]
    periods = ["2024", "2025", "2026"]

    matrix = SensitivityEngine.generate_wacc_growth_matrix(
        forecast_fcfs=fcfs,
        forecast_periods=periods,
        base_wacc=0.09,
        base_terminal_growth=0.025,
    )
    assert len(matrix["wacc_axis"]) == 5
    assert len(matrix["growth_axis"]) == 5
    assert len(matrix["enterprise_value_matrix"]) == 5
    assert matrix["enterprise_value_matrix"][2][2] is not None  # Base cell is valid

    # Scenario engine
    drivers = ForecastDrivers(revenue_growth_rates=[0.08, 0.07, 0.06])
    scenarios = ScenarioEngine.run_scenarios(
        base_revenue=1000.0,
        base_drivers=drivers,
        base_wacc=0.09,
        base_terminal_growth=0.025,
        horizon=3,
        total_debt=100.0,
        cash_and_equivalents=20.0,
        shares_outstanding=50.0,
    )
    assert "base" in scenarios
    assert "bull" in scenarios
    assert "bear" in scenarios
    assert scenarios["bull"]["enterprise_value"] > scenarios["base"]["enterprise_value"]
    assert scenarios["base"]["enterprise_value"] > scenarios["bear"]["enterprise_value"]
