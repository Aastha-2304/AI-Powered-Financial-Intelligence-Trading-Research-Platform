"""
Back-testing and forecast error metrics:
- Mean Absolute Percentage Error (MAPE) with epsilon handling for zero/near-zero actuals:
  MAPE = mean( |actual - predicted| / max(|actual|, epsilon) )
- Root Mean Squared Error (RMSE):
  RMSE = sqrt( mean( (actual - predicted)^2 ) )
- Mean Absolute Error (MAE):
  MAE = mean( |actual - predicted| )
- Back-testing harness on held-out historical periods.
"""
from typing import List, Dict, Tuple, Optional, Any
import numpy as np

EPSILON = 1e-4  # Epsilon prevents zero division in MAPE calculation


class BacktestMetrics:
    """Calculates backtest error metrics with epsilon protection."""

    @staticmethod
    def calculate_mape(actuals: List[float], predictions: List[float], epsilon: float = EPSILON) -> float:
        """
        Calculates MAPE safely handling zero and near-zero actuals.
        Returns percentage (0.05 = 5%).
        """
        if not actuals or not predictions or len(actuals) != len(predictions):
            return 0.0
        errors = [
            abs(act - pred) / max(abs(act), epsilon)
            for act, pred in zip(actuals, predictions)
        ]
        return float(np.mean(errors))

    @staticmethod
    def calculate_rmse(actuals: List[float], predictions: List[float]) -> float:
        """Calculates Root Mean Squared Error."""
        if not actuals or not predictions or len(actuals) != len(predictions):
            return 0.0
        sq_errors = [(act - pred) ** 2 for act, pred in zip(actuals, predictions)]
        return float(np.sqrt(np.mean(sq_errors)))

    @staticmethod
    def calculate_mae(actuals: List[float], predictions: List[float]) -> float:
        """Calculates Mean Absolute Error."""
        if not actuals or not predictions or len(actuals) != len(predictions):
            return 0.0
        errors = [abs(act - pred) for act, pred in zip(actuals, predictions)]
        return float(np.mean(errors))

    @classmethod
    def evaluate_model_backtest(
        cls,
        history: List[float],
        holdout_count: int = 1,
        growth_rate: float = 0.05,
    ) -> Dict[str, Any]:
        """
        Splits historical series into training and hold-out test periods,
        forecasts the holdout using Naive, Exponential Smoothing, and Driver Model,
        and computes comparative error metrics.
        """
        if len(history) <= holdout_count:
            return {"error": "Insufficient history for holdout back-test."}

        train = history[:-holdout_count]
        actuals = history[-holdout_count:]
        horizon = len(actuals)

        # Baseline 1: Naive (last observed value)
        naive_preds = [train[-1]] * horizon

        # Baseline 2: Holt / Exponential Smoothing
        from app.forecasting.baselines import BaselineForecastEngine
        exp_preds = BaselineForecastEngine.forecast_exponential_smoothing(train, horizon=horizon)

        # Driver Model: Extrapolate from last train using assumed growth rate
        driver_preds = []
        val = train[-1]
        for _ in range(horizon):
            val = val * (1.0 + growth_rate)
            driver_preds.append(val)

        return {
            "holdout_count": holdout_count,
            "actuals": [round(x, 2) for x in actuals],
            "naive": {
                "predictions": [round(x, 2) for x in naive_preds],
                "mape": round(cls.calculate_mape(actuals, naive_preds), 4),
                "rmse": round(cls.calculate_rmse(actuals, naive_preds), 2),
                "mae": round(cls.calculate_mae(actuals, naive_preds), 2),
            },
            "exponential_smoothing": {
                "predictions": [round(x, 2) for x in exp_preds],
                "mape": round(cls.calculate_mape(actuals, exp_preds), 4),
                "rmse": round(cls.calculate_rmse(actuals, exp_preds), 2),
                "mae": round(cls.calculate_mae(actuals, exp_preds), 2),
            },
            "driver_model": {
                "predictions": [round(x, 2) for x in driver_preds],
                "mape": round(cls.calculate_mape(actuals, driver_preds), 4),
                "rmse": round(cls.calculate_rmse(actuals, driver_preds), 2),
                "mae": round(cls.calculate_mae(actuals, driver_preds), 2),
            },
        }
