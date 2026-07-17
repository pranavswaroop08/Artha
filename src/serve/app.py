"""FastAPI serving layer for Artha predictions.

v1 uses a deterministic MockPredictor when no trained artifact is present
(env ARTHA_MODEL_PATH unset), and the MockLLMClient for the explanation. When a
model bundle IS provided, the API serves REAL point forecasts + split-conformal
return intervals (no more hardcoded return_ci_low/high).
"""
from __future__ import annotations

import os
import time
from pathlib import Path

import pandas as pd
import numpy as np
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, HTMLResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from .models import ContributingFactor, PredictionRequest, PredictionResponse
from ..nlp.llm_client import MockLLMClient
from ..monitoring import metrics
from ..common.context import get_logger
from ..models.ml.lightgbm_trainer import LightGBMTrainer

logger = get_logger(__name__)

app = FastAPI(title="Artha Quant Platform API", version="0.1.0")

# Allow the frontend (opened via file:// or any origin in local dev) to call the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

llm_client = MockLLMClient()

# Serve the frontend HTML at the root URL so the browser and API share one origin.
FRONTEND_HTML = Path(__file__).resolve().parents[2] / "frontend" / "index.html"

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def serve_frontend():
    if FRONTEND_HTML.exists():
        return HTMLResponse(content=FRONTEND_HTML.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h2>Artha API is running. Frontend not found at frontend/index.html</h2>")


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

# Optional feature store (real parquet produced by scripts/ingest.py). When set
# and a model is loaded, /predict looks up the ACTUAL feature row for the
# requested symbol/date instead of fabricating inputs.
FEATURES_PATH = os.environ.get("ARTHA_FEATURES_PATH")
_feature_store: pd.DataFrame | None = None
if FEATURES_PATH:
    try:
        _feature_store = pd.read_parquet(FEATURES_PATH)
        _feature_store["event_ts"] = pd.to_datetime(_feature_store["event_ts"])
        logger.info("feature_store_loaded", rows=len(_feature_store),
                    symbols=_feature_store["symbol"].nunique())
    except Exception as exc:
        logger.warning("feature_store_load_failed", error=str(exc))
        _feature_store = None


def _build_model_row(symbol: str, as_of_ts: str) -> pd.DataFrame | None:
    """Return the exact feature row the trained model expects for (symbol, date).

    Builds columns matching model.feature_cols: a 'rank_feat_*' entry is the
    within-day cross-sectional percentile rank of the underlying 'feat_*'; a
    raw 'feat_*' entry (macro/context, constant within a day) is passed through
    as-is. This mirrors scripts/train.py's preprocess exactly. Returns None if
    the symbol/date is not in the store.
    """
    if _feature_store is None or _model is None:
        return None
    ts = pd.to_datetime(as_of_ts).normalize()
    day = _feature_store["event_ts"].dt.normalize()
    mask = (_feature_store["symbol"] == symbol) & (day == ts)
    row = _feature_store.loc[mask]
    if row.empty:
        return None
    row = row.iloc[0:1].copy()

    out = {}
    for mcol in _model.feature_cols:
        if mcol.startswith("rank_feat_"):
            base = "feat_" + mcol[len("rank_feat_"):]
            if base not in _feature_store.columns:
                out[mcol] = 0.5
                continue
            r = _feature_store.loc[day == ts, base].rank(pct=True, method="average")
            out[mcol] = float(r.loc[row.index].iloc[0])
        elif mcol.startswith("feat_"):
            out[mcol] = float(row[mcol].iloc[0]) if mcol in row else 0.0
        else:
            out[mcol] = 0.0
    return pd.DataFrame(out, index=[0])



def _probs_from_return(ret: float, sigma: float) -> tuple[float, float, float]:
    """Map a predicted return to up/flat/down probabilities via a normal CDF.

    prob_up = P(ret > +eps), prob_down = P(ret < -eps), prob_flat = remainder,
    with eps a tiny classification threshold. With IC~0 the return clusters near
    0, so probs stay honest (close to a no-edge ~1/3 each).
    """
    from math import erf, sqrt
    eps = 1e-4

    def cdf(x: float) -> float:
        return 0.5 * (1.0 + erf(x / (sigma * sqrt(2.0))))

    p_up = 1.0 - cdf(eps - ret / sigma) if sigma > 0 else (0.5 if ret > 0 else 0.0)
    p_down = cdf(-eps - ret / sigma) if sigma > 0 else (0.5 if ret < 0 else 0.0)
    p_up = float(p_up)
    p_down = float(p_down)
    p_flat = max(0.0, 1.0 - p_up - p_down)
    # renormalise to exactly 1.0
    tot = p_up + p_down + p_flat
    return p_up / tot, p_down / tot, p_flat / tot


def _real_factors(model: LightGBMTrainer, row: pd.DataFrame) -> list[ContributingFactor]:
    """Top contributing factors from the model's feature importances.

    Uses LightGBM SHAP contributions when available (faithful per-row attri-
    bution); falls back to global importance x sign of the (ranked) value.
    """
    try:
        contrib = model.model.predict(row, pred_contrib=True)
        # contrib shape: (1, n_features + 1); last column is the bias.
        vals = np.asarray(contrib[0][:-1], dtype=float)
        cols = model.feature_cols
        pairs = sorted(zip(cols, vals), key=lambda x: abs(x[1]), reverse=True)[:4]
        out = []
        for c, v in pairs:
            out.append(ContributingFactor(
                feature=c, impact=round(float(v), 4),
                direction="up" if v > 0 else ("down" if v < 0 else "neutral"),
            ))
        return out
    except Exception:
        imp = model.model.feature_importances_
        cols = model.feature_cols
        pairs = sorted(zip(cols, imp), key=lambda x: x[1], reverse=True)[:4]
        return [ContributingFactor(feature=c, impact=round(float(i) / max(imp) * 0.2, 4),
                                   direction="up") for c, i in pairs]


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

    # ── Real model path: look up the ACTUAL feature row and infer on it ──────
    if _model is not None:
        row = _build_model_row(req.symbol, req.as_of_ts)
        if row is None:
            # No real features for this symbol/date -> do NOT fabricate a signal.
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=422,
                content={"detail": (
                    f"No feature row for symbol={req.symbol} as_of_ts={req.as_of_ts}. "
                    "The model only covers symbols/dates present in the feature store."
                )},
            )

        iv = _model.predict_interval(row)[0]
        expected_return = float(iv.point)
        ci_low, ci_high = float(iv.lower), float(iv.upper)
        half_width = (ci_high - ci_low) / 2.0

        # sigma from the conformal residual half-width (honest uncertainty).
        sigma = half_width if half_width > 0 else 0.02
        prob_up, prob_down, prob_flat = _probs_from_return(expected_return, sigma)

        action = (
            "LONG_PARTIAL" if prob_up > 0.55
            else ("SHORT_PARTIAL" if prob_down > 0.55 else "HOLD")
        )
        # Confidence inversely related to interval width (wider = less sure).
        confidence = float(max(0.0, min(1.0, 1.0 - half_width / 0.10)))
        factors = _real_factors(_model, row)
        model_version = "lgbm-conformal-0.1.0"
        # Regime: crude read from the predicted return sign/magnitude.
        regime = "risk_on_trending" if expected_return > 0 else "risk_off_choppy"
        explanation = (
            f"{req.symbol}: model expects ~{expected_return:.1%} over 5 days "
            f"(90% CI [{ci_low:.1%}, {ci_high:.1%}]); "
            f"top drivers {', '.join(f.feature for f in factors[:2])}. "
            f"[real-model]"
        )
        metrics.PREDICT_REQUESTS.labels(recommended_action=action).inc()
        metrics.PREDICTION_CONFIDENCE.observe(confidence)
        return PredictionResponse(
            symbol=req.symbol, as_of_ts=req.as_of_ts, horizon_days=5,
            prob_up=prob_up, prob_down=prob_down, prob_flat=prob_flat,
            expected_return=round(expected_return, 4),
            return_ci_low=round(ci_low, 4), return_ci_high=round(ci_high, 4),
            confidence=round(confidence, 3), risk_score=round(min(1.0, half_width / 0.10), 3),
            suggested_stop_loss_pct=round(-half_width, 4),
            suggested_take_profit_pct=round(half_width, 4),
            recommended_action=action, position_size_pct=round(confidence * 3.0, 2),
            top_contributing_factors=factors, explanation=explanation,
            model_version=model_version, regime=regime,
        )

    # ── Mock path (no model wired): clearly labelled, no fabricated alt-data ─
    h = sum(ord(c) for c in req.symbol) % 100
    prob_up, prob_down, prob_flat = _deterministic_probs(req.symbol)
    confidence = 0.71
    action = "LONG_PARTIAL" if prob_up > 0.5 else "HOLD"
    metrics.PREDICT_REQUESTS.labels(recommended_action=action).inc()
    metrics.PREDICTION_CONFIDENCE.observe(confidence)

    factors = [
        ContributingFactor(feature="rank_feat_ret_5d", impact=0.12, direction="up"),
        ContributingFactor(feature="rank_feat_vol_21d", impact=-0.06, direction="down"),
    ]
    llm_out = llm_client.parse_news([
        f"{req.symbol}: mock regime supports an expected move."
    ])
    expected_return = round(0.01 + (h / 100) * 0.05, 3)
    ci_low, ci_high = round(expected_return - 0.024, 3), round(expected_return + 0.031, 3)

    explanation = (
        f"{req.symbol}: MOCK model expects ~{expected_return:.1%} over 5 days "
        f"(90% CI [{ci_low:.1%}, {ci_high:.1%}]); "
        f"top drivers rank_feat_ret_5d (+) and rank_feat_vol_21d (-). "
        f"[{llm_out[0]['impact_type']}] [MOCK - no ARTHA_MODEL_PATH set]"
    )

    return PredictionResponse(
        symbol=req.symbol, as_of_ts=req.as_of_ts, horizon_days=5,
        prob_up=prob_up, prob_down=prob_down, prob_flat=prob_flat,
        expected_return=expected_return, return_ci_low=ci_low, return_ci_high=ci_high,
        confidence=confidence, risk_score=0.42,
        suggested_stop_loss_pct=-0.045, suggested_take_profit_pct=0.062,
        recommended_action=action, position_size_pct=1.8,
        top_contributing_factors=factors, explanation=explanation,
        model_version="mock-0.1.0", regime="risk_on_trending",
    )



@app.get("/metrics", response_class=PlainTextResponse)
def get_metrics():
    """Prometheus scrape endpoint."""
    return PlainTextResponse(
        generate_latest(metrics.REGISTRY), media_type=CONTENT_TYPE_LATEST
    )
