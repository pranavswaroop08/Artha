"""Tests for conformal prediction + trainer persistence/interval predict."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.models.ml.conformal import ConformalPredictor
from src.models.ml.lightgbm_trainer import LightGBMTrainer
from src.training.walk_forward import WalkForwardCV


def test_conformal_coverages_expected():
    """Under exchangeable residuals, realized coverage ~>= 1-alpha."""
    rng = np.random.default_rng(0)
    y_true = rng.normal(0, 1, 4000)
    y_pred = y_true + rng.normal(0, 0.3, 4000)  # model + noise
    cp = ConformalPredictor(alpha=0.1).fit(y_true, y_pred)
    # Calibrate interval half-width: |residual| quantile
    half = cp._quantile()
    in_band = (y_true >= y_pred - half) & (y_true <= y_pred + half)
    assert in_band.mean() >= 0.82  # marginal coverage ~>= 1-alpha (0.9)


def test_conformal_predict_centers_on_point():
    cp = ConformalPredictor(alpha=0.1).fit(np.array([0.0, 0.1, 0.2]), np.array([0.0, 0.1, 0.2]))
    iv = cp.predict(0.05)
    assert iv.point == 0.05
    assert iv.lower <= iv.point <= iv.upper  # perfect-fit calibration -> width 0 is valid
    assert iv.width == pytest.approx(2 * cp._quantile())


def test_conformal_guardrails():
    with pytest.raises(ValueError, match="alpha"):
        ConformalPredictor(alpha=1.1)
    cp = ConformalPredictor(alpha=0.1)
    with pytest.raises(ValueError, match="fit"):
        cp.predict(0.0)
    with pytest.raises(ValueError, match="non-empty"):
        ConformalPredictor(alpha=0.1).fit(np.array([]), np.array([]))


def _make_signal_df(n=420, seed=1):
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2026-01-01", periods=n)
    df = pd.DataFrame({
        "symbol": ["T"] * n,
        "event_ts": dates,
        "feat_x": rng.normal(0, 1, n),
        "feat_y": rng.normal(0, 1, n),
    })
    # Strong, clean linear signal so walk-forward IC is robustly positive.
    z = df["feat_x"] * 1.2 - df["feat_y"] * 0.8
    df["target_fwd_ret_5d"] = (z - z.mean()) / z.std() * 0.05 + rng.normal(0, 0.005, n)
    df["target_fwd_ret_5d"] = df["target_fwd_ret_5d"].shift(-5)
    return df


def test_trainer_train_evaluate_enriches_results_and_conformal():
    cv = WalkForwardCV(n_splits=3, train_size_days=200, test_size_days=60, gap_days=5)
    tr = LightGBMTrainer(target_col="target_fwd_ret_5d",
                         feature_cols=["feat_x", "feat_y"])
    res = tr.train_and_evaluate(_make_signal_df(), cv)
    # Conformal pipeline is wired and returns sane values.
    assert 0.0 < res["conformal_coverage"] <= 1.0
    assert res["conformal_half_width"] >= 0.0
    assert res["n_test_samples"] > 0


def test_trainer_save_load_and_predict_interval(tmp_path):
    df = _make_signal_df()
    cv = WalkForwardCV(n_splits=3, train_size_days=200, test_size_days=60, gap_days=5)
    tr = LightGBMTrainer(target_col="target_fwd_ret_5d",
                         feature_cols=["feat_x", "feat_y"])
    tr.train_and_evaluate(df, cv)

    path = tmp_path / "model.joblib"
    tr.save(str(path))

    loaded = LightGBMTrainer.load(str(path))
    assert loaded.model is not None
    assert loaded.conformal is not None

    # predict + interval on a fresh frame
    pts = loaded.predict(df.iloc[:10])
    ivs = loaded.predict_interval(df.iloc[:10])
    assert pts.shape[0] == 10
    assert len(ivs) == 10
    for iv in ivs:
        assert iv.lower < iv.point < iv.upper


def test_predict_requires_training():
    tr = LightGBMTrainer()
    with pytest.raises(RuntimeError, match="train_and_evaluate"):
        tr.predict(pd.DataFrame({"feat_x": [1.0]}))
