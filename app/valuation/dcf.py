"""
Discounted Cash Flow (DCF) valuation engine:
- Multi-period Free Cash Flow discounting: PV = FCF_t / (1 + WACC)^t
- Constant-Growth Gordon Terminal Value:
  Terminal Value = FCF_n * (1 + g) / (WACC - g)
  PV of Terminal Value = Terminal Value / (1 + WACC)^n
- Non-negotiable Guard:
  Strictly reject calculation if WACC <= terminal_growth_rate.
- Enterprise Value (EV) = PV of Forecast FCFs + PV of Terminal Value
- Equity Value Bridge:
  Equity Value = Enterprise Value - Total Debt + Cash & Cash Equivalents + Non-Operating Adjustments
- Implied Share Price = Equity Value / Shares Outstanding
"""
from typing import List, Dict, Optional
from pydantic import BaseModel, Field


class DCFGuardError(ValueError):
    """Raised when mathematical preconditions of DCF are violated (e.g. WACC <= g)."""
    pass


class DCFValuationResult(BaseModel):
    """Complete auditable DCF valuation output."""
    forecast_periods: List[str]
    forecast_fcfs: List[float]
    discount_factors: List[float]
    pv_forecast_fcfs: List[float]
    sum_pv_fcfs: float
    final_year_fcf: float
    terminal_growth_rate: float
    wacc: float
    terminal_value_undiscounted: float
    pv_terminal_value: float
    enterprise_value: float
    total_debt: float
    cash_and_equivalents: float
    other_adjustments: float
    equity_value: float
    shares_outstanding: Optional[float] = None
    implied_share_price: Optional[float] = None


class DCFValuationEngine:
    """Deterministic Discounted Cash Flow valuation engine."""

    @classmethod
    def calculate_dcf(
        cls,
        forecast_fcfs: List[float],
        forecast_periods: List[str],
        wacc: float,
        terminal_growth_rate: float,
        total_debt: float = 0.0,
        cash_and_equivalents: float = 0.0,
        other_adjustments: float = 0.0,
        shares_outstanding: Optional[float] = None,
    ) -> DCFValuationResult:
        """
        Executes DCF valuation with strict terminal growth guard and enterprise-to-equity bridge.
        """
        if not forecast_fcfs:
            raise ValueError("forecast_fcfs list cannot be empty.")
        if len(forecast_fcfs) != len(forecast_periods):
            raise ValueError("forecast_fcfs and forecast_periods must have matching lengths.")

        # Non-negotiable Blueprint Guard: Require WACC > terminal_growth_rate
        if wacc <= terminal_growth_rate:
            raise DCFGuardError(
                f"DCF Guard Violation: WACC ({wacc:.2%}) must be strictly greater than "
                f"terminal growth rate ({terminal_growth_rate:.2%}) to avoid negative/infinite valuation."
            )

        n = len(forecast_fcfs)
        discount_factors: List[float] = []
        pv_forecast_fcfs: List[float] = []

        # 1. Discount explicit forecast FCFs
        for t in range(1, n + 1):
            df = 1.0 / ((1.0 + wacc) ** t)
            discount_factors.append(round(df, 6))
            pv_fcf = forecast_fcfs[t - 1] * df
            pv_forecast_fcfs.append(round(pv_fcf, 2))

        sum_pv_fcfs = sum(pv_forecast_fcfs)

        # 2. Terminal Value (Gordon Constant Growth)
        # TV_n = FCF_n * (1 + g) / (WACC - g)
        final_fcf = forecast_fcfs[-1]
        tv_undiscounted = (final_fcf * (1.0 + terminal_growth_rate)) / (wacc - terminal_growth_rate)
        
        # PV of Terminal Value = TV_n / (1 + WACC)^n
        final_df = 1.0 / ((1.0 + wacc) ** n)
        pv_tv = tv_undiscounted * final_df

        # 3. Enterprise Value = Sum(PV of FCFs) + PV of Terminal Value
        enterprise_value = sum_pv_fcfs + pv_tv

        # 4. Enterprise-to-Equity Bridge
        # Equity Value = EV - Debt + Cash + Adjustments
        equity_value = enterprise_value - total_debt + cash_and_equivalents + other_adjustments

        # 5. Implied Share Price
        implied_price = None
        if shares_outstanding and shares_outstanding > 0:
            implied_price = round(equity_value / shares_outstanding, 2)

        return DCFValuationResult(
            forecast_periods=forecast_periods,
            forecast_fcfs=[round(x, 2) for x in forecast_fcfs],
            discount_factors=discount_factors,
            pv_forecast_fcfs=pv_forecast_fcfs,
            sum_pv_fcfs=round(sum_pv_fcfs, 2),
            final_year_fcf=round(final_fcf, 2),
            terminal_growth_rate=round(terminal_growth_rate, 4),
            wacc=round(wacc, 4),
            terminal_value_undiscounted=round(tv_undiscounted, 2),
            pv_terminal_value=round(pv_tv, 2),
            enterprise_value=round(enterprise_value, 2),
            total_debt=round(total_debt, 2),
            cash_and_equivalents=round(cash_and_equivalents, 2),
            other_adjustments=round(other_adjustments, 2),
            equity_value=round(equity_value, 2),
            shares_outstanding=shares_outstanding,
            implied_share_price=implied_price,
        )
