"""Tests for the FastAPI serving layer."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.serve.app import app
from src.serve.models import PredictionResponse

client = TestClient(app)

REQUIRED_FIELDS = [
    "symbol", "as_of_ts", "horizon_days", "prob_up", "prob_down", "prob_flat",
    "expected_return", "return_ci_low", "return_ci_high", "confidence",
    "risk_score", "suggested_stop_loss_pct", "suggested_take_profit_pct",
    "recommended_action", "position_size_pct", "top_contributing_factors",
    "explanation", "model_version", "regime",
]


def test_health_still_works_with_middleware():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "healthy"}


def test_real_model_serves_conformal_intervals(tmp_path, monkeypatch):
    """When ARTHA_MODEL_PATH is set, /predict uses real conformal CIs."""
    import pandas as pd
    import numpy as np
    from src.models.ml.lightgbm_trainer import LightGBMTrainer
    from src.training.walk_forward import WalkForwardCV

    rng = np.random.default_rng(3)
    n = 360
    df = pd.DataFrame({
        "symbol": ["T"] * n,
        "event_ts": pd.date_range("2026-01-01", periods=n),
        "feat_x": rng.normal(0, 1, n),
        "feat_y": rng.normal(0, 1, n),
    })
    z = df["feat_x"] * 1.0 - df["feat_y"] * 0.5
    df["target_fwd_ret_5d"] = ((z - z.mean()) / z.std()) * 0.05
    df["target_fwd_ret_5d"] = df["target_fwd_ret_5d"].shift(-5)

    tr = LightGBMTrainer(target_col="target_fwd_ret_5d",
                         feature_cols=["feat_x", "feat_y"])
    cv = WalkForwardCV(n_splits=3, train_size_days=180, test_size_days=40, gap_days=5)
    tr.train_and_evaluate(df, cv)
    path = tmp_path / "m.joblib"
    tr.save(str(path))

    monkeypatch.setenv("ARTHA_MODEL_PATH", str(path))
    from src.serve import app as serve_app
    import importlib
    importlib.reload(serve_app)
    real_client = TestClient(serve_app.app)

    r = real_client.post("/predict", json={"symbol": "RELIANCE", "as_of_ts": "2026-07-16T00:00:00Z"})
    assert r.status_code == 200
    d = r.json()
    assert d["model_version"] == "lgbm-conformal-0.1.0"
    assert d["return_ci_low"] < d["return_ci_high"]
    assert d["return_ci_low"] <= d["expected_return"] <= d["return_ci_high"]


def test_predict_endpoint_schema():
    r = client.post(
        "/predict",
        json={"symbol": "RELIANCE", "as_of_ts": "2026-07-16T15:30:00+05:30"},
    )
    assert r.status_code == 200
    data = r.json()
    for f in REQUIRED_FIELDS:
        assert f in data, f"Missing field: {f}"
    assert data["top_contributing_factors"]
    assert "feature" in data["top_contributing_factors"][0]
    assert len(data["explanation"]) > 0


@pytest.mark.parametrize("symbol", ["RELIANCE", "TCS", "INFY", "A", "ZZZZZZ", "hdfc"])
def test_probabilities_valid_and_sum_to_one(symbol):
    """Across many symbols: each prob in [0,1] and the three sum to exactly 1.0."""
    r = client.post("/predict", json={"symbol": symbol, "as_of_ts": "2026-07-16T00:00:00Z"})
    assert r.status_code == 200
    d = r.json()
    for k in ("prob_up", "prob_down", "prob_flat"):
        assert 0.0 <= d[k] <= 1.0, f"{k}={d[k]} out of range for {symbol}"
    assert abs(d["prob_up"] + d["prob_down"] + d["prob_flat"] - 1.0) < 1e-9


def test_deterministic_same_symbol_same_output():
    body = {"symbol": "RELIANCE", "as_of_ts": "2026-07-16T00:00:00Z"}
    a = client.post("/predict", json=body).json()
    b = client.post("/predict", json=body).json()
    assert a == b


def test_empty_symbol_rejected():
    r = client.post("/predict", json={"symbol": "", "as_of_ts": "2026-07-16T00:00:00Z"})
    assert r.status_code == 422  # pydantic min_length


def test_response_model_rejects_bad_probabilities():
    """The Pydantic contract itself must reject a non-normalized distribution."""
    with pytest.raises(ValueError, match="sum to 1.0"):
        PredictionResponse(
            symbol="X", as_of_ts="t", horizon_days=5,
            prob_up=0.9, prob_down=0.3, prob_flat=0.3,  # sums to 1.5
            expected_return=0.0, return_ci_low=-0.01, return_ci_high=0.01,
            confidence=0.5, risk_score=0.5, suggested_stop_loss_pct=-0.04,
            suggested_take_profit_pct=0.06, recommended_action="HOLD",
            position_size_pct=1.0, top_contributing_factors=[],
            explanation="x", model_version="v", regime="r",
        )
