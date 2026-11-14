"""
Statistical anomaly detection engine for financial time-series:
- Z-score and Interquartile Range (IQR) outliers on Year-over-Year (YoY) percentage changes
- Outliers are treated strictly as WARNINGS (anomalies), never as hard failures,
  because real companies experience exceptional events (acquisitions, write-downs, restructuring).
"""
import numpy as np
from typing import List, Dict, Tuple, Optional
from app.schemas.financial import FinancialFact
from app.schemas.modeling import ValidationFinding

Z_SCORE_THRESHOLD = 3.0  # standard deviations from mean
IQR_MULTIPLIER = 2.5     # conservative multiplier to prevent high false alarms on small series


class AnomalyDetector:
    """Detects statistical outliers in financial line item time series."""

    @staticmethod
    def detect_series_anomalies(
        line_item: str,
        facts_sorted_by_period: List[FinancialFact],
        run_id: str,
        dataset_id: str,
        dataset_version: int,
    ) -> List[ValidationFinding]:
        """
        Calculates YoY changes and evaluates Z-score / IQR.
        Emits warning findings for extreme jumps (e.g. >500% jump or 3-sigma deviation).
        """
        findings: List[ValidationFinding] = []
        if len(facts_sorted_by_period) < 3:
            # Need at least 3 periods for meaningful statistical variance
            return findings

        values = [f.normalized_value for f in facts_sorted_by_period]
        periods = [f.period for f in facts_sorted_by_period]

        # Calculate year-on-year growth rates
        yoy_rates = []
        for i in range(1, len(values)):
            prev = values[i - 1]
            curr = values[i]
            if prev != 0:
                yoy = (curr - prev) / abs(prev)
                yoy_rates.append((periods[i], yoy, curr, prev, facts_sorted_by_period[i].source_row))

        if len(yoy_rates) < 2:
            return findings

        rates = [r[1] for r in yoy_rates]
        mean_rate = np.mean(rates)
        std_rate = np.std(rates)

        # IQR calculation
        q25, q75 = np.percentile(rates, [25, 75])
        iqr = q75 - q25
        lower_bound = q25 - (IQR_MULTIPLIER * iqr)
        upper_bound = q75 + (IQR_MULTIPLIER * iqr)

        for period, rate, curr, prev, row_idx in yoy_rates:
            is_anomaly = False
            reason = ""

            # Check Z-score if std is non-zero
            if std_rate > 1e-4:
                z = abs(rate - mean_rate) / std_rate
                if z >= Z_SCORE_THRESHOLD:
                    is_anomaly = True
                    reason = f"Z-score = {z:.2f} (threshold {Z_SCORE_THRESHOLD})"

            # Check IQR bounds if iqr is non-zero
            if not is_anomaly and iqr > 1e-4:
                if rate < lower_bound or rate > upper_bound:
                    is_anomaly = True
                    reason = f"Outside IQR bounds [{lower_bound:.1%}, {upper_bound:.1%}]"

            # Check raw extreme jump (>500% jump)
            if not is_anomaly and abs(rate) >= 5.0 and abs(curr - prev) > 1e6:
                is_anomaly = True
                reason = f"Extreme year-on-year shift ({rate:+.1%})"

            if is_anomaly:
                findings.append(
                    ValidationFinding(
                        finding_id=f"vf_anom_{line_item}_{period}_{run_id}",
                        run_id=run_id,
                        dataset_id=dataset_id,
                        dataset_version=dataset_version,
                        rule_name="statistical_outlier_yoy",
                        dimension="anomaly_severity",
                        severity="warning",  # Non-negotiable: Outlier is a warning, not a hard error
                        line_item=line_item,
                        period=period,
                        observed_value=curr,
                        expected_value=prev,
                        tolerance=None,
                        message=f"Statistical anomaly in {line_item} ({period}): {reason}. Value moved from {prev:,.2f} to {curr:,.2f} ({rate:+.1%}).",
                        source_row=row_idx,
                    )
                )

        return findings
