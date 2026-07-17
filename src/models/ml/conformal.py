"""Split conformal prediction for return intervals.

Turns OOS residuals from walk-forward folds into marginal prediction intervals
around point forecasts. The conformal guarantee holds under exchangeability of
the calibration residual set: with miscoverage alpha, P(y in interval) >= 1-alpha.

This replaces the hardcoded return_ci_low/return_ci_high in the serving layer
with empirically justified intervals.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class ConformalInterval:
    point: float
    lower: float
    upper: float
    coverage: float  # 1 - alpha used

    @property
    def width(self) -> float:
        return self.upper - self.lower

    def to_dict(self) -> dict:
        return {
            "point": self.point,
            "lower": self.lower,
            "upper": self.upper,
            "coverage": self.coverage,
        }


class ConformalPredictor:
    """Split-conformal regression intervals from a calibration residual set.

    Fit on OOS residuals (y_true - y_pred) gathered across walk-forward folds.
    Then call predict() on fresh point forecasts to center intervals on them.
    """

    def __init__(self, alpha: float = 0.1):
        if not 0.0 < alpha < 1.0:
            raise ValueError("alpha must be in (0, 1)")
        self.alpha = alpha
        self._cal_residuals: Optional[np.ndarray] = None

    def fit(self, y_true: np.ndarray, y_pred: np.ndarray) -> "ConformalPredictor":
        y_true = np.asarray(y_true, dtype=float)
        y_pred = np.asarray(y_pred, dtype=float)
        if y_true.shape != y_pred.shape or y_true.size == 0:
            raise ValueError("y_true and y_pred must be equal-length, non-empty")
        self._cal_residuals = y_true - y_pred
        return self

    def _quantile(self) -> float:
        """Conformal quantile (Romano et al. 2019, finite-sample corrected).

        Returns the (1-alpha)-quantile of |residual| under the "leave-one-out"
        factor (n+1)/n, which yields marginal coverage >= 1-alpha.
        """
        n = self._cal_residuals.size
        q_level = min(1.0, (1.0 - self.alpha) * (n + 1) / n)
        return float(np.quantile(np.abs(self._cal_residuals), q_level))

    def calibrate(self, y_true: np.ndarray, y_pred: np.ndarray) -> "ConformalPredictor":
        return self.fit(y_true, y_pred)

    def predict(self, point: float) -> ConformalInterval:
        if self._cal_residuals is None:
            raise ValueError("Call fit() with calibration residuals first")
        half = self._quantile()
        return ConformalInterval(
            point=float(point),
            lower=float(point - half),
            upper=float(point + half),
            coverage=1.0 - self.alpha,
        )

    def predict_batch(self, points: np.ndarray) -> list[ConformalInterval]:
        return [self.predict(float(p)) for p in np.asarray(points, dtype=float)]
