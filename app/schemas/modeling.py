"""
Validation, forecasting, valuation, and report metadata schemas.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ValidationFinding(BaseModel):
    """Specific rule check finding or statistical anomaly."""
    finding_id: str
    run_id: str
    dataset_id: str
    dataset_version: int
    rule_name: str
    dimension: str  # completeness, mapping_quality, accounting_consistency, anomaly_severity
    severity: str  # warning, hard_failure
    line_item: Optional[str] = None
    period: Optional[str] = None
    observed_value: Optional[float] = None
    expected_value: Optional[float] = None
    tolerance: Optional[float] = None
    message: str
    source_row: Optional[int] = None


class ValidationRun(BaseModel):
    """Execution summary for a dataset quality evaluation."""
    run_id: str
    dataset_id: str
    dataset_version: int
    completeness_score: float
    mapping_quality_score: float
    accounting_consistency_score: float
    anomaly_severity_score: float
    overall_quality_score: float
    has_hard_failures: bool = False
    total_findings: int = 0
    executed_at: datetime = Field(default_factory=datetime.utcnow)


class AssumptionSet(BaseModel):
    """Versioned driver and macro assumptions for forecasting and DCF."""
    assumption_set_id: str
    company_id: str
    version: int
    source: str = "user_input"
    is_approved: bool = True
    assumptions_json: Dict[str, Any]
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ForecastRun(BaseModel):
    """Saved forecast output."""
    forecast_id: str
    dataset_id: str
    dataset_version: int
    assumption_set_id: str
    model_name: str  # driver_based, naive, exp_smoothing
    horizon_periods: int
    results_json: Dict[str, Any]
    backtest_metrics_json: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ValuationRun(BaseModel):
    """Saved DCF and scenario valuation result."""
    valuation_id: str
    dataset_id: str
    dataset_version: int
    forecast_id: str
    assumption_set_id: str
    wacc: float
    terminal_growth_rate: float
    enterprise_value: float
    equity_value: float
    implied_share_price: Optional[float] = None
    sensitivity_grid_json: Dict[str, Any]
    scenarios_json: Dict[str, Any]
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ReportRecord(BaseModel):
    """Metadata for generated report document."""
    report_id: str
    company_id: str
    dataset_id: str
    dataset_version: int
    forecast_id: Optional[str] = None
    valuation_id: Optional[str] = None
    report_type: str  # docx, pdf
    file_path: str
    generation_time_seconds: float
    created_at: datetime = Field(default_factory=datetime.utcnow)
