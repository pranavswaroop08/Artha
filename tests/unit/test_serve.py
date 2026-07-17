"""Tests for the FastAPI serving layer.

These tests are hermetic: an autouse fixture forces the module into MOCK state
(no ARTHA_MODEL_PATH / ARTHA_FEATURES_PATH) before every test, so the module-
level `client` is always a mock predictor. Real-model tests set the env vars,
reload the module, and build their own client.
"""
from __future__ import annotations

import importlib

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.serve import app as serve_app

REQUIRED_FIELDS = [
    "symbol", "as_of_ts", "horizon_days", "prob_up", "prob_down", "prob_flat",
    "expected_return", "return_ci_low", "return_ci_high", "confidence",
    "risk_score", "suggested_stop_loss_pct", "suggested_take_profit_pct",
    "recommended_action", "position_size_pct", "top_contributing_factors",
    "explanation", "model_version", "regime",
]


@pytest.fixture(autouse=True)
def _mock_state(monkeypatch):
    """Force mock mode (no model/feature-store env) before each test."""
    monkeypatch.delenv("ARTHA_MODEL_PATH", raising=False)
    monkeypatch.delenv("ARTHA_FEATURES_PATH", raising=False)
    importlib.reload(serve_app)
    yield
    monkeypatch.delenv("ARTHA_MODEL_PATH", raising=False)
    monkeypatch.delenv("ARTHA_FEATURES_PATH", raising=False)
    importlib.reload(serve_app)


@pytest.fixture
def client():
    return TestClient(serve_app.app)


def test_health_still_works_with_middleware(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "healthy"}


def test_predict_endpoint_schema(client):
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
def test_probabilities_valid_and_sum_to_one(client, symbol):
    r = client.post("/predict", json={"symbol": symbol, "as_of_ts": "2026-07-16T00:00:00Z"})
    assert r.status_code == 200
    d = r.json()
    for k in ("prob_up", "prob_down", "prob_flat"):
        assert 0.0 <= d[k] <= 1.0, f"{k}={d[k]} out of range for {symbol}"
    assert abs(d["prob_up"] + d["prob_down"] + d["prob_flat"] - 1.0) < 1e-9


def test_deterministic_same_symbol_same_output(client):
    body = {"symbol": "RELIANCE", "as_of_ts": "2026-07-16T00:00:00Z"}
    a = client.post("/predict", json=body).json()
    b = client.post("/predict", json=body).json()
    assert a == b


def test_empty_symbol_rejected(client):
    r = client.post("/predict", json={"symbol": "", "as_of_ts": "2026-07-16T00:00:00Z"})
    assert r.status_code == 422  # pydantic min_length


def test_mock_factors_do_not_claim_alt_data(client):
    """Mock mode must not invent FII/PCR features it doesn't have."""
    r = client.post("/predict", json={"symbol": "RELIANCE", "as_of_ts": "2026-07-16T00:00:00Z"})
    feats = [f["feature"] for f in r.json()["top_contributing_factors"]]
    assert "fii_net_buy_5d" not in feats
    assert "options_pcr" not in feats


def _make_model(tmp_path, feature_cols, rank=True):
    """Train a tiny walk-forward model and return (model_path, store_df)."""
    rng = np.random.default_rng(4)
    n = 360
    days = pd.date_range("2026-01-01", periods=n)
    df = pd.DataFrame({
        "symbol": ["T"] * n,
        "event_ts": days,
        "feat_x": rng.normal(0, 1, n),
        "feat_y": rng.normal(0, 1, n),
    })
    if rank:
        # include both raw and rank columns in the store
        df["rank_feat_x"] = df.groupby("event_ts")["feat_x"].rank(pct=True)
        df["rank_feat_y"] = df.groupby("event_ts")["feat_y"].rank(pct=True)
    z = df["feat_x"] * 1.0 - df["feat_y"] * 0.5
    df["target_fwd_ret_5d"] = ((z - z.mean()) / z.std()) * 0.05
    df["target_fwd_ret_5d"] = df["target_fwd_ret_5d"].shift(-5)

    from src.models.ml.lightgbm_trainer import LightGBMTrainer
    from src.training.walk_forward import WalkForwardCV

    tr = LightGBMTrainer(target_col="target_fwd_ret_5d", feature_cols=feature_cols)
    cv = WalkForwardCV(n_splits=3, train_size_days=180, test_size_days=40, gap_days=5)
    tr.train_and_evaluate(df, cv)
    model_path = tmp_path / "m.joblib"
    tr.save(str(model_path))
    return model_path, df


def test_real_model_serves_conformal_intervals(tmp_path, monkeypatch):
    """With ARTHA_MODEL_PATH + ARTHA_FEATURES_PATH, /predict uses real CIs."""
    model_path, df = _make_model(tmp_path, ["rank_feat_x", "rank_feat_y"], rank=True)
    store = tmp_path / "features.parquet"
    df.to_parquet(store)

    monkeypatch.setenv("ARTHA_MODEL_PATH", str(model_path))
    monkeypatch.setenv("ARTHA_FEATURES_PATH", str(store))
    importlib.reload(serve_app)
    c = TestClient(serve_app.app)

    r = c.post("/predict", json={"symbol": "T", "as_of_ts": "2026-03-01"})
    assert r.status_code == 200
    d = r.json()
    assert d["model_version"] == "lgbm-conformal-0.1.0"
    assert d["return_ci_low"] < d["return_ci_high"]
    assert d["return_ci_low"] <= d["expected_return"] <= d["return_ci_high"]


def test_real_model_uses_feature_store_row(tmp_path, monkeypatch):
    """Real model infers on the ACTUAL feature row; unknown symbol -> 422."""
    model_path, df = _make_model(tmp_path, ["rank_feat_x", "rank_feat_y"], rank=True)
    store = tmp_path / "features.parquet"
    df.to_parquet(store)

    monkeypatch.setenv("ARTHA_MODEL_PATH", str(model_path))
    monkeypatch.setenv("ARTHA_FEATURES_PATH", str(store))
    importlib.reload(serve_app)
    c = TestClient(serve_app.app)

    r = c.post("/predict", json={"symbol": "T", "as_of_ts": "2026-03-01"})
    assert r.status_code == 200
    d = r.json()
    assert d["model_version"] == "lgbm-conformal-0.1.0"
    assert d["return_ci_low"] <= d["expected_return"] <= d["return_ci_high"]
    assert abs(d["prob_up"] + d["prob_down"] + d["prob_flat"] - 1.0) < 1e-9
    feats = [f["feature"] for f in d["top_contributing_factors"]]
    assert all(f in ("rank_feat_x", "rank_feat_y") for f in feats)
    assert "fii_net_buy" not in str(feats)
    # Unknown symbol -> 422, not a fabricated prediction.
    r2 = c.post("/predict", json={"symbol": "NOPE", "as_of_ts": "2026-03-01"})
    assert r2.status_code == 422


def test_response_model_rejects_bad_probabilities():
    """The Pydantic contract itself must reject a non-normalized distribution."""
    from src.serve.models import PredictionResponse
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
