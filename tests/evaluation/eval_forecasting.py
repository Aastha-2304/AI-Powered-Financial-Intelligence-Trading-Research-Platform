"""
Evaluation script for Phase 4 Forecasting Engine.
Runs comparative holdout back-testing over historical corporate revenue series:
- Naive model vs Exponential Smoothing (Holt linear) vs Driver-Based model.
- Calculates MAPE (with epsilon zero protection) and RMSE.
- Appends reproducible benchmark metrics to evaluation_results.md for project report citation.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.forecasting.backtest import BacktestMetrics


def run_forecasting_evaluation() -> dict:
    # Historical multi-year revenue series (5 years historical, 1 held-out test year)
    # 2019: 100M, 2020: 108M, 2021: 118M, 2022: 128M, 2023 (Held-out Actual): 140M
    history = [100.0, 108.0, 118.0, 128.0, 140.0]

    # Evaluate backtest using 1 held-out year and 8% driver growth assumption
    backtest = BacktestMetrics.evaluate_model_backtest(
        history=history,
        holdout_count=1,
        growth_rate=0.08,
    )
    return backtest


def append_forecasting_results(results: dict):
    results_path = PROJECT_ROOT / "evaluation_results.md"
    existing_content = results_path.read_text(encoding="utf-8") if results_path.exists() else ""

    naive = results["naive"]
    exp = results["exponential_smoothing"]
    driver = results["driver_model"]

    addition = f"""
## 3. Module: Financial Statement Forecasting Engine
- **Evaluation Date**: 2026-10-28
- **Historical Back-test Setup**: 5-period corporate revenue series with 1 held-out actual validation period
- **Actual Held-Out Figure**: {results['actuals'][0]:,.2f}
- **MAPE Formula**: `mean( |actual - predicted| / max(|actual|, 1e-4) )` (safe for near-zero denominators)

### Model Comparison Table:
| Model Architecture | Predicted Value | MAPE (%) | RMSE | MAE |
| :--- | :---: | :---: | :---: | :---: |
| **Naive Baseline (Last Value)** | {naive['predictions'][0]:,.2f} | {naive['mape'] * 100:.2f}% | {naive['rmse']:.2f} | {naive['mae']:.2f} |
| **Exponential Smoothing (Holt Linear)** | {exp['predictions'][0]:,.2f} | {exp['mape'] * 100:.2f}% | {exp['rmse']:.2f} | {exp['mae']:.2f} |
| **Driver-Based Model (8% Assumed Growth)** | {driver['predictions'][0]:,.2f} | {driver['mape'] * 100:.2f}% | {driver['rmse']:.2f} | {driver['mae']:.2f} |

---
"""
    results_path.write_text(existing_content + addition, encoding="utf-8")
    print(f"Appended Phase 4 forecasting evaluation metrics to {results_path}")


if __name__ == "__main__":
    res = run_forecasting_evaluation()
    print("Forecasting Evaluation Results:", res)
    append_forecasting_results(res)
