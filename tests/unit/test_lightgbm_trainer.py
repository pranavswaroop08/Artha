"""Tests for the baseline LightGBM trainer (real training runs)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.models.ml.lightgbm_trainer import LightGBMTrainer
from src.training.walk_forward import WalkForwardCV


@pytest.fixture
def synthetic_data_with_signal() -> pd.DataFrame:
    """400 days, one symbol. Target has a real dependence on features so a
    correctly-wired trainer must achieve positive OOS IC."""
    rng = np.random.default_rng(42)
    n = 400
    dates = pd.date_range("2026-01-01", periods=n)
    feat_x = rng.normal(0, 1, n)
    feat_y = rng.normal(0, 1, n)
    # Strong linear signal + modest noise.
    target = 0.6 * feat_x - 0.3 * feat_y + rng.normal(0, 0.2, n)
    return pd.DataFrame(
        {
            "symbol": ["TEST"] * n,
            "event_ts": dates,
            "feat_x": feat_x,
            "feat_y": feat_y,
            "target_fwd_ret_5d": target,
        }
    )


def test_trainer_runs_and_returns_metrics(synthetic_data_with_signal):
    cv = WalkForwardCV(n_splits=3, train_size_days=200, test_size_days=40, gap_days=5)
    trainer = LightGBMTrainer(
        target_col="target_fwd_ret_5d", feature_cols=["feat_x", "feat_y"]
    )
    res = trainer.train_and_evaluate(synthetic_data_with_signal, cv)

    assert set(res) >= {"oos_rmse", "oos_ic", "mean_fold_ic", "n_folds", "n_test_samples"}
    assert res["n_folds"] == 3
    assert res["n_test_samples"] > 0
    assert res["oos_rmse"] > 0


def test_trainer_learns_the_signal(synthetic_data_with_signal):
    """With a genuine signal, OOS IC must be clearly positive."""
    cv = WalkForwardCV(n_splits=3, train_size_days=200, test_size_days=40, gap_days=5)
    trainer = LightGBMTrainer(feature_cols=["feat_x", "feat_y"])
    res = trainer.train_and_evaluate(synthetic_data_with_signal, cv)
    assert res["oos_ic"] > 0.3, f"expected positive OOS IC, got {res['oos_ic']}"


def test_feature_autodetect_from_prefix(synthetic_data_with_signal):
    """When feature_cols omitted, columns starting with 'feat_' are used."""
    cv = WalkForwardCV(n_splits=2, train_size_days=200, test_size_days=40, gap_days=5)
    trainer = LightGBMTrainer()  # no feature_cols
    res = trainer.train_and_evaluate(synthetic_data_with_signal, cv)
    assert set(trainer.feature_cols) == {"feat_x", "feat_y"}
    assert res["n_folds"] == 2


def test_missing_target_raises(synthetic_data_with_signal):
    cv = WalkForwardCV(n_splits=2, train_size_days=200, test_size_days=40, gap_days=5)
    trainer = LightGBMTrainer(target_col="does_not_exist", feature_cols=["feat_x"])
    with pytest.raises(ValueError, match="Target column"):
        trainer.train_and_evaluate(synthetic_data_with_signal, cv)


def test_no_feature_cols_raises():
    df = pd.DataFrame(
        {
            "symbol": ["T"] * 300,
            "event_ts": pd.date_range("2026-01-01", periods=300),
            "target_fwd_ret_5d": np.random.default_rng(0).normal(0, 1, 300),
        }
    )
    cv = WalkForwardCV(n_splits=2, train_size_days=200, test_size_days=40, gap_days=5)
    trainer = LightGBMTrainer()  # no feat_ columns exist
    with pytest.raises(ValueError, match="No feature columns"):
        trainer.train_and_evaluate(df, cv)
