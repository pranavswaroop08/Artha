#!/usr/bin/env python
"""Artha Model Training Script — features.parquet -> trained model bundle.

Runs a LightGBM cross-sectional forecaster using walk-forward CV with purged
gaps, calibrates split-conformal return intervals on OOS residuals, then saves
the bundle so the FastAPI server can load it via ARTHA_MODEL_PATH.

Key design choices
------------------
* Cross-sectional rank normalization: each feature is replaced by its
  within-day percentile rank across all symbols. This makes LightGBM learn
  "which stock is relatively strongest today" rather than absolute price levels
  that shift with market regimes — the standard technique for cross-sectional
  equity models.
* Expanding walk-forward window: train on all history up to fold boundary to
  maximise signal on longer-horizon targets.
* Conformal calibration: OOS residuals → guaranteed 90% return intervals.

Usage:
    python scripts/train.py                          # default 5d target
    python scripts/train.py --target target_fwd_ret_1d
    python scripts/train.py --target target_fwd_ret_21d
    python scripts/train.py --folds 5 --train-days 750 --test-days 125
    python scripts/train.py --no-rank               # skip rank normalisation
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd

from src.models.ml.lightgbm_trainer import LightGBMTrainer
from src.training.walk_forward import WalkForwardCV
from src.common.context import get_logger

logger = get_logger("train")

DEFAULT_FEATURES = PROJECT_ROOT / "data" / "offline" / "features.parquet"
DEFAULT_OUT      = PROJECT_ROOT / "models" / "lgbm_5d.joblib"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Train Artha LightGBM model.")
    p.add_argument("--features", type=str, default=str(DEFAULT_FEATURES))
    p.add_argument("--target", type=str, default="target_fwd_ret_5d")
    p.add_argument("--out", type=str, default=str(DEFAULT_OUT))
    p.add_argument("--folds", type=int, default=5)
    p.add_argument("--train-days", type=int, default=750,
                   help="Training window in trading days per fold (default: 750 = ~3yr).")
    p.add_argument("--test-days", type=int, default=125,
                   help="Test window in trading days per fold (default: 125 = ~6mo).")
    p.add_argument("--gap-days", type=int, default=5)
    p.add_argument("--expanding", action="store_true", default=True,
                   help="Expanding train window (default: True).")
    p.add_argument("--n-estimators", type=int, default=500)
    p.add_argument("--alpha", type=float, default=0.1)
    p.add_argument("--no-rank", action="store_true",
                   help="Skip cross-sectional rank normalisation.")
    p.add_argument("--decay-halflife", type=float, default=504,
                   help="Recency decay half-life in TRADING days for training "
                        "sample weights (default 504 ~= 2y). 0 disables decay. "
                        "Down-weights stale regime data to fight non-stationarity.")
    p.add_argument("--no-save", action="store_true")
    return p.parse_args()


# ── Cross-sectional rank normalisation ────────────────────────────────────────
def add_cs_rank_features(df: pd.DataFrame, feat_cols: list[str]) -> tuple[pd.DataFrame, list[str]]:
    """Replace each feature with its within-day percentile rank [0,1].

    This is the single most impactful preprocessing step for cross-sectional
    equity models: it removes regime-level scale shifts and makes the model
    learn relative ordering across symbols on the same day.

    Returns (df_with_rank_cols, rank_col_names).
    """
    rank_cols = []
    for col in feat_cols:
        rcol = f"rank_{col}"
        df[rcol] = (
            df.groupby("event_ts")[col]
            .rank(pct=True, method="average", na_option="keep")
        )
        rank_cols.append(rcol)
    return df, rank_cols


# ── Extra metrics ──────────────────────────────────────────────────────────────
def directional_accuracy(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    mask = y_true != 0
    if mask.sum() == 0:
        return float("nan")
    return float((np.sign(y_true[mask]) == np.sign(y_pred[mask])).mean())


def main() -> int:
    args = parse_args()

    # ── Load data ──────────────────────────────────────────────────────────
    feat_path = Path(args.features)
    if not feat_path.exists():
        print(f"[ERROR] Features file not found: {feat_path}")
        print("  Run:  python scripts/ingest.py  first.")
        return 1

    print(f"\n{'='*62}")
    print("  Artha -- Model Training")
    print(f"{'='*62}")

    df = pd.read_parquet(feat_path)
    raw_feat_cols = sorted(c for c in df.columns if c.startswith("feat_"))

    n_symbols   = df["symbol"].nunique()
    n_dates     = df["event_ts"].dt.date.nunique()
    date_min    = df["event_ts"].min().date()
    date_max    = df["event_ts"].max().date()

    print(f"  Data          : {len(df):,} rows | {n_symbols} symbols | {n_dates} trading days")
    print(f"  Date range    : {date_min} -> {date_max}")
    print(f"  Target        : {args.target}")
    print(f"  Base features : {len(raw_feat_cols)}")

    if args.target not in df.columns:
        print(f"[ERROR] Target '{args.target}' not found.")
        return 1

    # ── Cross-sectional rank features ──────────────────────────────────────
    # Columns that vary across symbols on the same day are ranked (the
    # cross-sectional signal). Columns that are constant within a day -- e.g.
    # market-regime macro (VIX, Nifty level, USDINR) -- carry NO cross-sectional
    # rank info, so they are passed through RAW (their level/change is the
    # signal). Auto-detect by within-day variance.
    const_within_day = []
    varying_within_day = []
    for col in raw_feat_cols:
        # variance of the column across symbols within each day; if always ~0
        # the column is a macro/context feature.
        day_var = df.groupby("event_ts")[col].transform("nunique")
        if (day_var <= 1).all():
            const_within_day.append(col)
        else:
            varying_within_day.append(col)

    if not args.no_rank:
        df, rank_cols = add_cs_rank_features(df, varying_within_day)
        feat_cols = rank_cols + const_within_day   # ranks + raw macro context
        print(f"  CS rank feats : {len(rank_cols)} ranks + {len(const_within_day)} raw "
              f"macro/context (constant-within-day)")
    else:
        feat_cols = raw_feat_cols
        print("  CS rank feats : disabled (--no-rank)")

    horizon_map = {"target_fwd_ret_1d": 1, "target_fwd_ret_5d": 5,
                   "target_fwd_ret_21d": 21}
    horizon = horizon_map.get(args.target, args.gap_days)
    out_tag = args.target.replace("target_fwd_ret_", "").replace("d", "")

    print(f"  CV folds      : {args.folds} x "
          f"(train={args.train_days}d | gap={args.gap_days}d | test={args.test_days}d)")
    print(f"  Expanding win : {args.expanding}")
    print(f"  n_estimators  : {args.n_estimators}")
    print(f"  Conformal CI  : {(1-args.alpha)*100:.0f}%")
    print(f"  Recency decay : {args.decay_halflife if args.decay_halflife > 0 else 'off'} "
          f"trading-day half-life")
    print()

    # ── Walk-forward CV ────────────────────────────────────────────────────
    cv = WalkForwardCV(
        n_splits=args.folds,
        train_size_days=args.train_days,
        test_size_days=args.test_days,
        gap_days=args.gap_days,
        expanding=args.expanding,
    )
    try:
        cv.validate_gap_for_horizon(horizon)
    except ValueError as e:
        print(f"[ERROR] {e}")
        return 1

    # ── Train ──────────────────────────────────────────────────────────────
    trainer = LightGBMTrainer(
        target_col=args.target,
        feature_cols=feat_cols,
        n_estimators=args.n_estimators,
        conformal_alpha=args.alpha,
        decay_halflife_days=args.decay_halflife,
        mlflow_experiment="artha-lgbm-baseline",
        params={
            "objective":         "regression",
            "metric":            "rmse",
            "learning_rate":     0.03,
            "num_leaves":        63,
            "min_child_samples": 30,
            "subsample":         0.8,
            "subsample_freq":    1,
            "colsample_bytree":  0.7,
            "reg_alpha":         0.1,
            "reg_lambda":        1.0,
            "verbose":           -1,
            "n_jobs":            -1,
            "seed":              42,
        },
    )

    print("Training... (this takes ~10-30s)")
    results = trainer.train_and_evaluate(df, cv)

    # ── Extra metrics ──────────────────────────────────────────────────────
    da = directional_accuracy(
        np.asarray(trainer.oos_true), np.asarray(trainer.oos_pred)
    )

    importances = None
    if trainer.model is not None:
        importances = sorted(
            zip(feat_cols, trainer.model.feature_importances_),
            key=lambda x: x[1], reverse=True,
        )

    # ── Print results ──────────────────────────────────────────────────────
    ic     = results["oos_ic"]
    f_ic   = results["mean_fold_ic"]
    rmse   = results["oos_rmse"]
    hw     = results["conformal_half_width"]
    cov    = results["conformal_coverage"]

    print()
    print(f"{'='*62}")
    print("  RESULTS  (Out-of-Sample, walk-forward purged CV)")
    print(f"{'='*62}")
    print(f"  OOS RMSE              : {rmse:.6f}")
    print(f"  OOS IC  (Pearson)     : {ic:+.4f}   (target: 0.03-0.08)")
    print(f"  Mean fold IC          : {f_ic:+.4f}")
    print(f"  Directional accuracy  : {da:.2%}   (target: 55-62%)")
    print(f"  OOS samples           : {results['n_test_samples']:,}")
    print(f"  Folds completed       : {results['n_folds']}")
    print(f"  Conformal interval    : +/-{hw:.4f}  ({cov:.0%} coverage)")

    if importances:
        print()
        print("  Top feature importances:")
        max_imp = max(v for _, v in importances)
        for feat, imp in importances[:10]:
            bar = "#" * int(imp / max_imp * 25)
            print(f"    {feat:<30} {imp:>6.0f}  {bar}")

    print(f"{'='*62}")

    # ── Signal quality assessment ──────────────────────────────────────────
    print()
    if ic >= 0.05:
        print(f"[STRONG] IC={ic:.4f}  -- solid signal, proceed to backtest.")
    elif ic >= 0.02:
        print(f"[OK]     IC={ic:.4f}  -- usable signal, proceed to backtest.")
    elif ic >= 0.0:
        print(f"[WEAK]   IC={ic:.4f}  -- marginal, backtest to check cost-adjusted edge.")
    else:
        print(f"[NEGATIVE] IC={ic:.4f}  -- see fold breakdown above.")
        print("  Fold ICs printed above. A single bad fold can drag the aggregate.")
        print("  Check: mean_fold_ic. If that's positive, signal exists but is regime-sensitive.")

    if f_ic >= 0.03:
        print(f"  Mean fold IC={f_ic:.4f} is in target range -- the signal is real.")

    # ── Save ───────────────────────────────────────────────────────────────
    if not args.no_save:
        out_path = Path(args.out)
        # Auto-name by target if using default
        if str(args.out) == str(DEFAULT_OUT) and "5d" not in args.target:
            tag = out_tag
            if args.decay_halflife and args.decay_halflife > 0:
                tag += f"_decay{int(args.decay_halflife)}"
            out_path = PROJECT_ROOT / "models" / f"lgbm_{tag}d.joblib"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        trainer.save(str(out_path))
        print()
        print(f"  Model saved -> {out_path}")
        print()
        print("  Next steps:")
        print(f"    Backtest:  python scripts/backtest.py --model {out_path}")
        print(f"    Serve:     $env:ARTHA_MODEL_PATH = \"{out_path}\"")
        print(f"               uvicorn src.serve.app:app --reload")

    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
