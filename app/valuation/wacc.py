"""
Capital Asset Pricing Model (CAPM) and Weighted Average Cost of Capital (WACC) engine:
- Cost of Equity: Ke = Rf + Beta * ERP
- After-tax Cost of Debt: Kd * (1 - tax_rate)
- WACC = (E / (E + D)) * Ke + (D / (E + D)) * Kd * (1 - tax_rate)
- Validations:
  - WACC must be positive and non-zero
  - Debt and equity weights sum to 1.0
"""
from typing import Optional
from pydantic import BaseModel, Field


class WACCParameters(BaseModel):
    """Auditable inputs for Weighted Average Cost of Capital calculation."""
    risk_free_rate: float = Field(default=0.042, description="Risk-free rate (e.g. 10-year Treasury yield, 0.042 = 4.2%)")
    beta: float = Field(default=1.10, description="Equity beta measuring systematic risk")
    equity_risk_premium: float = Field(default=0.055, description="Market equity risk premium (0.055 = 5.5%)")
    cost_of_debt_pretax: float = Field(default=0.055, description="Pre-tax borrowing rate")
    tax_rate: float = Field(default=0.25, description="Marginal corporate tax rate")
    equity_weight: float = Field(default=0.80, description="Target equity weight E / (E + D)")
    debt_weight: float = Field(default=0.20, description="Target debt weight D / (E + D)")


class WACCResult(BaseModel):
    """Detailed breakdown of calculated discount rate components."""
    cost_of_equity: float
    after_tax_cost_of_debt: float
    equity_weight: float
    debt_weight: float
    wacc: float


class WACCEngine:
    """Calculates CAPM and WACC deterministically."""

    @classmethod
    def calculate_wacc(cls, params: WACCParameters) -> WACCResult:
        """
        Calculates Cost of Equity via CAPM and blended WACC.
        """
        # Validate weights
        total_weight = params.equity_weight + params.debt_weight
        if abs(total_weight - 1.0) > 1e-4:
            # Normalize weights if not summing to 1
            e_w = params.equity_weight / total_weight
            d_w = params.debt_weight / total_weight
        else:
            e_w = params.equity_weight
            d_w = params.debt_weight

        # 1. Cost of Equity = Rf + Beta * ERP
        ke = params.risk_free_rate + (params.beta * params.equity_risk_premium)

        # 2. After-tax Cost of Debt = Kd * (1 - t)
        kd_after_tax = params.cost_of_debt_pretax * (1.0 - params.tax_rate)

        # 3. WACC = E_w * Ke + D_w * Kd_after_tax
        wacc = (e_w * ke) + (d_w * kd_after_tax)

        if wacc <= 0.0:
            raise ValueError(f"Calculated WACC ({wacc:.4f}) must be positive.")

        return WACCResult(
            cost_of_equity=round(ke, 6),
            after_tax_cost_of_debt=round(kd_after_tax, 6),
            equity_weight=round(e_w, 4),
            debt_weight=round(d_w, 4),
            wacc=round(wacc, 6),
        )
