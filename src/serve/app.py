"""FastAPI serving layer for Artha predictions.

v1 uses a deterministic MockPredictor when no trained artifact is present
(env ARTHA_MODEL_PATH unset), and the MockLLMClient for the explanation. When a
model bundle IS provided, the API serves REAL point forecasts + split-conformal
return intervals (no more hardcoded return_ci_low/high).
"""
from __future__ import annotations

import os
import time

import pandas as pd
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from .models import ContributingFactor, PredictionRequest, PredictionResponse
from ..nlp.llm_client import MockLLMClient
from ..monitoring import metrics
from ..common.context import get_logger
from ..models.ml.lightgbm_trainer import LightGBMTrainer

logger = get_logger(__name__)

app = FastAPI(title="Artha Quant Platform API", version="0.1.0")
llm_client = MockLLMClient()

# Optional real model bundle; falls back to mock when absent.
MODEL_PATH = os.environ.get("ARTHA_MODEL_PATH")
_model: LightGBMTrainer | None = None
if MODEL_PATH:
    try:
        _model = LightGBMTrainer.load(MODEL_PATH)
        logger.info("serving_real_model", path=MODEL_PATH)
    except Exception as exc:  # pragma: no cover - fail safe to mock
        logger.warning("model_load_failed_fallback_mock", error=str(exc))
        _model = None


@app.middleware("http")
async def track_latency(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    if request.url.path == "/predict" and request.method == "POST":
        metrics.PREDICT_LATENCY.observe(time.perf_counter() - start)
    return response


def _deterministic_probs(symbol: str) -> tuple[float, float, float]:
    """Stable per-symbol probabilities in [0,1] summing to exactly 1.0.

    Rounds prob_up/prob_down to 2 dp then derives prob_flat as the remainder,
    guaranteeing the three rounded values sum to 1.0 with all >= 0.
    """
    h = sum(ord(c) for c in symbol) % 100
    prob_up = round(0.34 + (h / 100) * 0.4, 2)   # 0.34..0.74
    prob_down = round(0.15 + ((h * 7) % 30) / 100, 2)  # 0.15..0.44
    prob_flat = round(1.0 - prob_up - prob_down, 2)
    if prob_flat < 0:  # renormalize defensively
        prob_up = round(prob_up + prob_flat, 2)
        prob_flat = 0.0
    return prob_up, prob_down, prob_flat


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.post("/predict", response_model=PredictionResponse)
def predict(req: PredictionRequest):
    logger.info("predict_request", symbol=req.symbol, as_of_ts=req.as_of_ts)

    h = sum(ord(c) for c in req.symbol) % 100
    prob_up, prob_down, prob_flat = _deterministic_probs(req.symbol)
    confidence = 0.71
    action = "LONG_PARTIAL" if prob_up > 0.5 else "HOLD"

    metrics.PREDICT_REQUESTS.labels(recommended_action=action).inc()
    metrics.PREDICTION_CONFIDENCE.observe(confidence)

    factors = [
        ContributingFactor(feature="fii_net_buy_5d", impact=0.12, direction="up"),
        ContributingFactor(feature="options_pcr", impact=-0.06, direction="down"),
    ]

    llm_out = llm_client.parse_news([
        f"{req.symbol}: FII inflows and options positioning support a "
        f"expected move."
    ])

    # Real model when a bundle is wired; otherwise deterministic mock expected return.
    if _model is not None:
        model_version = "lgbm-conformal-0.1.0"
        # Build a one-row feature frame keyed by the symbol's hash (mock features).
        # In production this is replaced by the feature store lookup at as_of_ts.
        feat_row = pd.DataFrame(
            {"feat_x": [(h % 100) / 50.0 - 1.0], "feat_y": [((h * 7) % 100) / 50.0 - 1.0]}
        )
        iv = _model.predict_interval(feat_row)[0]
        expected_return = round(float(iv.point), 3)
        ci_low, ci_high = round(float(iv.lower), 3), round(float(iv.upper), 3)
    else:
        model_version = "mock-0.1.0"
        expected_return = round(0.01 + (h / 100) * 0.05, 3)
        ci_low, ci_high = round(expected_return - 0.024, 3), round(expected_return + 0.031, 3)

    explanation = (
        f"{req.symbol}: model expects ~{expected_return:.1%} over 5 days "
        f"(90% CI [{ci_low:.1%}, {ci_high:.1%}]); "
        f"top drivers FII inflows (+) and put-call ratio (-). "
        f"[{llm_out[0]['impact_type']}]"
    )

    return PredictionResponse(
        symbol=req.symbol,
        as_of_ts=req.as_of_ts,
        horizon_days=5,
        prob_up=prob_up,
        prob_down=prob_down,
        prob_flat=prob_flat,
        expected_return=expected_return,
        return_ci_low=ci_low,
        return_ci_high=ci_high,
        confidence=confidence,
        risk_score=0.42,
        suggested_stop_loss_pct=-0.045,
        suggested_take_profit_pct=0.062,
        recommended_action=action,
        position_size_pct=1.8,
        top_contributing_factors=factors,
        explanation=explanation,
        model_version=model_version,
        regime="risk_on_trending",
    )


@app.get("/metrics", response_class=PlainTextResponse)
def get_metrics():
    """Prometheus scrape endpoint."""
    return PlainTextResponse(
        generate_latest(metrics.REGISTRY), media_type=CONTENT_TYPE_LATEST
    )
