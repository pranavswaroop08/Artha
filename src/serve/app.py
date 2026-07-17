"""FastAPI serving layer for Artha predictions.

v1 uses a deterministic MockPredictor (no trained artifact wired yet) and the
MockLLMClient for the human-readable explanation. Swap MockPredictor for an
MLflow-registry-loaded model when persistence lands.
"""
from __future__ import annotations

import time

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from .models import ContributingFactor, PredictionRequest, PredictionResponse
from ..nlp.llm_client import MockLLMClient
from ..monitoring import metrics
from ..common.context import get_logger

logger = get_logger(__name__)

app = FastAPI(title="Artha Quant Platform API", version="0.1.0")
llm_client = MockLLMClient()


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
    expected_return = round(0.01 + (h / 100) * 0.05, 3)
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
        f"{expected_return:.1%} expected move."
    ])
    explanation = (
        f"{req.symbol}: model expects ~{expected_return:.1%} over 5 days; "
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
        return_ci_low=round(expected_return - 0.024, 3),
        return_ci_high=round(expected_return + 0.031, 3),
        confidence=confidence,
        risk_score=0.42,
        suggested_stop_loss_pct=-0.045,
        suggested_take_profit_pct=0.062,
        recommended_action=action,
        position_size_pct=1.8,
        top_contributing_factors=factors,
        explanation=explanation,
        model_version="mock-0.1.0",
        regime="risk_on_trending",
    )


@app.get("/metrics", response_class=PlainTextResponse)
def get_metrics():
    """Prometheus scrape endpoint."""
    return PlainTextResponse(
        generate_latest(metrics.REGISTRY), media_type=CONTENT_TYPE_LATEST
    )
