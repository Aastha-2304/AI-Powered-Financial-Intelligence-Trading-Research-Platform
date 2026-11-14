"""
Sensitivity Matrix and Multi-Scenario Analysis Engine:
1. Sensitivity Heatmap: 2D grid varying WACC across rows and Terminal Growth Rate across columns.
2. Scenario Analysis: Base, Bull, and Bear cases using explicit saved operational drivers.
3. What-If Controls: Real-time slider evaluation for revenue growth, margins, WACC, and terminal growth.
"""
from typing import List, Dict, Any, Tuple, Optional
from app.valuation.dcf import DCFValuationEngine, DCFGuardError
from app.forecasting.drivers import ForecastDrivers, DriverForecastEngine


class SensitivityEngine:
    """Calculates WACC x Terminal Growth sensitivity matrices."""

    @classmethod
    def generate_wacc_growth_matrix(
        cls,
        forecast_fcfs: List[float],
        forecast_periods: List[str],
        base_wacc: float,
        base_terminal_growth: float,
        total_debt: float = 0.0,
        cash_and_equivalents: float = 0.0,
        shares_outstanding: Optional[float] = None,
        wacc_steps: List[float] = [-0.01, -0.005, 0.0, 0.005, 0.01],
        growth_steps: List[float] = [-0.01, -0.005, 0.0, 0.005, 0.01],
    ) -> Dict[str, Any]:
        """
        Builds a 5x5 sensitivity matrix grid evaluating Enterprise Value and Implied Share Price.
        Guards against invalid cells where WACC <= g.
        """
        wacc_values = [round(base_wacc + step, 4) for step in wacc_steps]
        growth_values = [round(base_terminal_growth + step, 4) for step in growth_steps]

        matrix_ev: List[List[Optional[float]]] = []
        matrix_share_price: List[List[Optional[float]]] = []

        for w in wacc_values:
            row_ev: List[Optional[float]] = []
            row_price: List[Optional[float]] = []
            for g in growth_values:
                if w <= g:
                    row_ev.append(None)
                    row_price.append(None)
                    continue

                try:
                    res = DCFValuationEngine.calculate_dcf(
                        forecast_fcfs=forecast_fcfs,
                        forecast_periods=forecast_periods,
                        wacc=w,
                        terminal_growth_rate=g,
                        total_debt=total_debt,
                        cash_and_equivalents=cash_and_equivalents,
                        shares_outstanding=shares_outstanding,
                    )
                    row_ev.append(res.enterprise_value)
                    row_price.append(res.implied_share_price)
                except DCFGuardError:
                    row_ev.append(None)
                    row_price.append(None)

            matrix_ev.append(row_ev)
            matrix_share_price.append(row_price)

        return {
            "wacc_axis": wacc_values,
            "growth_axis": growth_values,
            "enterprise_value_matrix": matrix_ev,
            "share_price_matrix": matrix_share_price,
        }


class ScenarioEngine:
    """Evaluates Base, Bull, and Bear operational scenarios."""

    @classmethod
    def run_scenarios(
        cls,
        base_revenue: float,
        base_drivers: ForecastDrivers,
        base_wacc: float,
        base_terminal_growth: float,
        start_year: int = 2024,
        horizon: int = 5,
        total_debt: float = 0.0,
        cash_and_equivalents: float = 0.0,
        shares_outstanding: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Builds Base, Bull (+3% growth, +2% EBIT margin, -0.5% WACC),
        and Bear (-3% growth, -2% EBIT margin, +0.5% WACC) valuations.
        """
        # Base Case
        base_proj = DriverForecastEngine.project_statements(base_revenue, base_drivers, start_year, horizon)
        base_fcfs = [p.free_cash_flow for p in base_proj]
        periods = [p.period for p in base_proj]
        base_dcf = DCFValuationEngine.calculate_dcf(
            base_fcfs, periods, base_wacc, base_terminal_growth,
            total_debt, cash_and_equivalents, 0.0, shares_outstanding
        )

        # Bull Case: accelerated growth, expanded margins, slightly lower WACC
        bull_rates = [r + 0.03 for r in base_drivers.revenue_growth_rates]
        bull_drivers = base_drivers.model_copy(update={
            "revenue_growth_rates": bull_rates,
            "cogs_percent_revenue": max(0.20, base_drivers.cogs_percent_revenue - 0.02),
        })
        bull_wacc = max(0.05, base_wacc - 0.005)
        bull_g = base_terminal_growth + 0.005
        bull_proj = DriverForecastEngine.project_statements(base_revenue, bull_drivers, start_year, horizon)
        bull_fcfs = [p.free_cash_flow for p in bull_proj]
        bull_dcf = DCFValuationEngine.calculate_dcf(
            bull_fcfs, periods, bull_wacc, bull_g,
            total_debt, cash_and_equivalents, 0.0, shares_outstanding
        )

        # Bear Case: compressed growth, higher COGS %, slightly higher WACC
        bear_rates = [max(-0.10, r - 0.03) for r in base_drivers.revenue_growth_rates]
        bear_drivers = base_drivers.model_copy(update={
            "revenue_growth_rates": bear_rates,
            "cogs_percent_revenue": min(0.85, base_drivers.cogs_percent_revenue + 0.02),
        })
        bear_wacc = base_wacc + 0.005
        bear_g = max(0.01, base_terminal_growth - 0.005)
        bear_proj = DriverForecastEngine.project_statements(base_revenue, bear_drivers, start_year, horizon)
        bear_fcfs = [p.free_cash_flow for p in bear_proj]
        bear_dcf = DCFValuationEngine.calculate_dcf(
            bear_fcfs, periods, bear_wacc, bear_g,
            total_debt, cash_and_equivalents, 0.0, shares_outstanding
        )

        return {
            "base": {
                "enterprise_value": base_dcf.enterprise_value,
                "equity_value": base_dcf.equity_value,
                "implied_share_price": base_dcf.implied_share_price,
                "wacc": base_wacc,
                "terminal_growth": base_terminal_growth,
            },
            "bull": {
                "enterprise_value": bull_dcf.enterprise_value,
                "equity_value": bull_dcf.equity_value,
                "implied_share_price": bull_dcf.implied_share_price,
                "wacc": bull_wacc,
                "terminal_growth": bull_g,
            },
            "bear": {
                "enterprise_value": bear_dcf.enterprise_value,
                "equity_value": bear_dcf.equity_value,
                "implied_share_price": bear_dcf.implied_share_price,
                "wacc": bear_wacc,
                "terminal_growth": bear_g,
            },
        }
