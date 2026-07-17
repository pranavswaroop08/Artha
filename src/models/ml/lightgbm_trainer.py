"""Baseline LightGBM trainer for cross-sectional return forecasting.

Uses WalkForwardCV (purged gaps) to evaluate strictly out-of-sample. Metrics:
RMSE (magnitude error) and IC (Pearson corr of prediction vs. realized return)
-- IC is the metric that actually matters for a trading signal.

MLflow is optional: if installed, params/metrics log to a local file store
(no server / Docker needed, per ADR-0003). If absent, training still runs and
returns metrics; logging is skipped with a warning.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.metrics import mean_squared_error
from scipy.stats import pearsonr

from ...common.context import get_logger
from ...training.walk_forward import WalkForwardCV

logger = get_logger(__name__)

try:
    import mlflow  # type: ignore

    _MLFLOW = True
except ImportError:  # pragma: no cover
    _MLFLOW = False


def _safe_ic(pred: np.ndarray, actual: np.ndarray) -> float:
    """Pearson IC that returns NaN instead of raising on degenerate input."""
    if len(pred) < 2:
        return float("nan")
    if np.std(pred) == 0 or np.std(actual) == 0:
        return float("nan")
    return float(pearsonr(pred, actual)[0])


class LightGBMTrainer:
    def __init__(
        self,
        target_col: str = "target_fwd_ret_5d",
        feature_cols: Optional[List[str]] = None,
        params: Optional[Dict[str, Any]] = None,
        n_estimators: int = 100,
        mlflow_experiment: Optional[str] = None,
    ):
        self.target_col = target_col
        self.feature_cols = feature_cols or []
        self.n_estimators = n_estimators
        self.mlflow_experiment = mlflow_experiment
        self.params = params or {
            "objective": "regression",
            "metric": "rmse",
            "learning_rate": 0.05,
            "num_leaves": 31,
            "verbose": -1,
            "n_jobs": 1,
            "seed": 42,
        }

    def train_and_evaluate(
        self, df: pd.DataFrame, cv: WalkForwardCV
    ) -> Dict[str, Any]:
        """Train per walk-forward fold, evaluate OOS, return aggregate metrics."""
        if self.target_col not in df.columns:
            raise ValueError(f"Target column '{self.target_col}' not found")

        if not self.feature_cols:
            self.feature_cols = [c for c in df.columns if c.startswith("feat_")]
        if not self.feature_cols:
            raise ValueError("No feature columns found (none start with 'feat_')")

        df_clean = df.dropna(
            subset=self.feature_cols + [self.target_col]
        ).reset_index(drop=True)

        oos_pred: List[float] = []
        oos_true: List[float] = []
        fold_ics: List[float] = []

        for i, (train_idx, test_idx) in enumerate(cv.split(df_clean)):
            train_df = df_clean.iloc[train_idx]
            test_df = df_clean.iloc[test_idx]
            X_tr, y_tr = train_df[self.feature_cols], train_df[self.target_col]
            X_te, y_te = test_df[self.feature_cols], test_df[self.target_col]

            model = lgb.LGBMRegressor(**self.params, n_estimators=self.n_estimators)
            model.fit(X_tr, y_tr)
            preds = model.predict(X_te)

            oos_pred.extend(preds)
            oos_true.extend(y_te.to_numpy())
            fold_ic = _safe_ic(np.asarray(preds), y_te.to_numpy())
            fold_ics.append(fold_ic)
            logger.info("fold_metrics", fold=i + 1, oos_ic=round(fold_ic, 4),
                        n_test=len(y_te))

        if not oos_true:
            raise ValueError("No folds produced test samples; check CV sizing.")

        pred_arr = np.asarray(oos_pred)
        true_arr = np.asarray(oos_true)
        rmse = float(np.sqrt(mean_squared_error(true_arr, pred_arr)))
        ic = _safe_ic(pred_arr, true_arr)
        mean_fold_ic = float(np.nanmean(fold_ics)) if fold_ics else float("nan")

        results = {
            "oos_rmse": rmse,
            "oos_ic": ic,
            "mean_fold_ic": mean_fold_ic,
            "n_folds": len(fold_ics),
            "n_test_samples": int(len(true_arr)),
        }
        logger.info("oos_summary", **{k: (round(v, 6) if isinstance(v, float) else v)
                                      for k, v in results.items()})

        self._maybe_log_mlflow(results)
        return results

    def _maybe_log_mlflow(self, results: Dict[str, Any]) -> None:
        if not _MLFLOW:
            logger.warning("mlflow_not_installed_skipping_logging")
            return
        try:
            if self.mlflow_experiment:
                mlflow.set_experiment(self.mlflow_experiment)
            with mlflow.start_run():
                mlflow.log_params({
                    "target_col": self.target_col,
                    "n_features": len(self.feature_cols),
                    "n_estimators": self.n_estimators,
                    **{f"lgb_{k}": v for k, v in self.params.items()},
                })
                mlflow.log_metrics({
                    k: v for k, v in results.items()
                    if isinstance(v, (int, float)) and not np.isnan(v)
                })
        except Exception as exc:  # pragma: no cover - logging must never break training
            logger.warning("mlflow_logging_failed", error=str(exc))
