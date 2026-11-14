"""
Driver-based financial forecasting engine.
Projects future income statement items, balance sheet working capital schedules,
and debt schedules based on explicit, auditable operational drivers:
- Revenue growth rate (%)
- Operating margin (EBIT %) or COGS % of revenue
- Tax rate (%)
- Working capital days (DSO, DIO, DPO)
- Net CapEx & D&A % of revenue
- Debt repayment schedule & interest rate
"""
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class ForecastDrivers(BaseModel):
    """Explicit, versioned operational assumptions driving projections."""
    revenue_growth_rates: List[float] = Field(
        default=[0.08, 0.07, 0.06, 0.05, 0.04],
        description="Annual revenue growth rates for each projection year (e.g. 0.08 = 8%)"
    )
    cogs_percent_revenue: float = Field(default=0.60, description="Cost of Goods Sold as % of Revenue")
    opex_percent_revenue: float = Field(default=0.18, description="Operating Expenses (SG&A, R&D) as % of Revenue")
    tax_rate: float = Field(default=0.25, description="Effective corporate tax rate (e.g. 0.25 = 25%)")
    da_percent_revenue: float = Field(default=0.04, description="Depreciation & Amortization as % of Revenue")
    capex_percent_revenue: float = Field(default=0.045, description="Capital Expenditures as % of Revenue")
    
    # Working capital drivers (days)
    days_sales_outstanding: float = Field(default=45.0, description="DSO (Accounts Receivable days)")
    days_inventory_outstanding: float = Field(default=40.0, description="DIO (Inventory days)")
    days_payable_outstanding: float = Field(default=35.0, description="DPO (Accounts Payable days)")
    
    # Debt schedule drivers
    existing_debt: float = Field(default=0.0, description="Starting total debt")
    annual_debt_repayment: float = Field(default=0.0, description="Fixed annual principal repayment")
    cost_of_debt: float = Field(default=0.05, description="Average borrowing interest rate")


class ForecastPeriodResult(BaseModel):
    """Forecasted line items for a specific projection period."""
    period: str
    year_index: int
    revenue: float
    cogs: float
    gross_profit: float
    operating_expenses: float
    operating_income: float  # EBIT
    interest_expense: float
    pretax_income: float
    tax_expense: float
    net_income: float
    depreciation_amortization: float
    capex: float
    accounts_receivable: float
    inventory: float
    accounts_payable: float
    net_working_capital: float
    change_in_nwc: float
    debt_balance: float
    free_cash_flow: float  # FCF = EBIT*(1-tax) + D&A - CapEx - Change in NWC


class DriverForecastEngine:
    """Projects multi-year financial statements using driver parameters."""

    @classmethod
    def project_statements(
        cls,
        base_revenue: float,
        drivers: ForecastDrivers,
        start_year: int = 2024,
        horizon: int = 5,
        starting_debt: Optional[float] = None,
        starting_nwc: Optional[float] = None,
    ) -> List[ForecastPeriodResult]:
        """
        Builds integrated multi-year projections of Income Statement,
        Working Capital, Debt, and Free Cash Flow.
        """
        results: List[ForecastPeriodResult] = []
        current_rev = base_revenue
        current_debt = starting_debt if starting_debt is not None else drivers.existing_debt

        # Establish base NWC from starting revenue
        prev_ar = (current_rev * drivers.days_sales_outstanding) / 365.0
        prev_inv = (current_rev * drivers.cogs_percent_revenue * drivers.days_inventory_outstanding) / 365.0
        prev_ap = (current_rev * drivers.cogs_percent_revenue * drivers.days_payable_outstanding) / 365.0
        prev_nwc = (prev_ar + prev_inv) - prev_ap if starting_nwc is None else starting_nwc

        # Ensure drivers list has enough rates
        rates = drivers.revenue_growth_rates
        if len(rates) < horizon:
            rates = rates + [rates[-1]] * (horizon - len(rates))

        for idx in range(horizon):
            proj_year = start_year + idx
            growth_rate = rates[idx]
            current_rev = current_rev * (1.0 + growth_rate)

            cogs = current_rev * drivers.cogs_percent_revenue
            gp = current_rev - cogs
            opex = current_rev * drivers.opex_percent_revenue
            ebit = gp - opex
            da = current_rev * drivers.da_percent_revenue
            capex = current_rev * drivers.capex_percent_revenue

            # Debt & interest schedule
            interest = current_debt * drivers.cost_of_debt
            pretax = ebit - interest
            tax = max(0.0, pretax * drivers.tax_rate)
            net_income = pretax - tax
            current_debt = max(0.0, current_debt - drivers.annual_debt_repayment)

            # Working capital schedules
            ar = (current_rev * drivers.days_sales_outstanding) / 365.0
            inv = (cogs * drivers.days_inventory_outstanding) / 365.0
            ap = (cogs * drivers.days_payable_outstanding) / 365.0
            nwc = (ar + inv) - ap
            change_in_nwc = nwc - prev_nwc
            prev_nwc = nwc

            # Free Cash Flow to Firm (FCFF) bridge:
            # FCF = EBIT * (1 - tax_rate) + D&A - CapEx - Delta NWC
            nopat = ebit * (1.0 - drivers.tax_rate)
            fcf = nopat + da - capex - change_in_nwc

            results.append(
                ForecastPeriodResult(
                    period=str(proj_year),
                    year_index=idx + 1,
                    revenue=round(current_rev, 2),
                    cogs=round(cogs, 2),
                    gross_profit=round(gp, 2),
                    operating_expenses=round(opex, 2),
                    operating_income=round(ebit, 2),
                    interest_expense=round(interest, 2),
                    pretax_income=round(pretax, 2),
                    tax_expense=round(tax, 2),
                    net_income=round(net_income, 2),
                    depreciation_amortization=round(da, 2),
                    capex=round(capex, 2),
                    accounts_receivable=round(ar, 2),
                    inventory=round(inv, 2),
                    accounts_payable=round(ap, 2),
                    net_working_capital=round(nwc, 2),
                    change_in_nwc=round(change_in_nwc, 2),
                    debt_balance=round(current_debt, 2),
                    free_cash_flow=round(fcf, 2),
                )
            )

        return results
