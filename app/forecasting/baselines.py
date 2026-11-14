"""
Statistical and naive baseline forecasting models:
1. Naive Baseline: Forecasts future periods as equal to the last observed historical period.
2. Moving Average Baseline: Average of past k periods.
3. Holt-Winters / Exponential Smoothing Baseline: Fits Holt's linear trend model using Statsmodels.
"""
from typing import List, Dict, Optional
import numpy as np
from statsmodels.tsa.api import SimpleExpSmoothing, Holt


class BaselineForecastEngine:
    """Provides simple, robust time-series baselines for comparison against driver models."""

    @staticmethod
    def forecast_naive(history: List[float], horizon: int = 5) -> List[float]:
        """Last observed value carried forward indefinitely."""
        if not history:
            return [0.0] * horizon
        last_val = history[-1]
        return [float(last_val)] * horizon

    @staticmethod
    def forecast_moving_average(history: List[float], window: int = 3, horizon: int = 5) -> List[float]:
        """Simple moving average of last k values carried forward."""
        if not history:
            return [0.0] * horizon
        k = min(len(history), window)
        avg = float(np.mean(history[-k:]))
        return [avg] * horizon

    @staticmethod
    def forecast_exponential_smoothing(history: List[float], horizon: int = 5) -> List[float]:
        """
        Fits Holt's exponential smoothing with linear trend when at least 3 points exist,
        falling back to simple exponential smoothing or naive otherwise.
        """
        if not history:
            return [0.0] * horizon
        if len(history) < 3:
            return BaselineForecastEngine.forecast_naive(history, horizon)

        try:
            # Fit Holt linear trend model
            model = Holt(history, initialization_method="estimated")
            fit = model.fit(optimized=True)
            forecast = fit.forecast(horizon)
            return [float(x) for x in forecast]
        except Exception:
            # Fallback to Simple Exponential Smoothing if trend fails to converge
            try:
                model_ses = SimpleExpSmoothing(history, initialization_method="estimated")
                fit_ses = model_ses.fit(optimized=True)
                forecast = fit_ses.forecast(horizon)
                return [float(x) for x in forecast]
            except Exception:
                return BaselineForecastEngine.forecast_naive(history, horizon)
