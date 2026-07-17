#!/usr/bin/env python
"""Artha Honest Evaluation — does the model have ALPHA, or just BETA?

Runs the trained model through the backtest engine in three configurations and
reports whether any profit is real skill:

  1. LONG-ONLY  (model predictions)   -- the naive, bull-market-flattering view
  2. MARKET-NEUTRAL (model, long/short) -- isolates alpha from market direction
  3. MARKET-NEUTRAL (RANDOM predictions) -- null check: if random does as well,
                                          the "signal" is beta, not skill

Then it computes:
  * Deflated Sharpe (Bailey-Pópelař) with multiple-testing correction
  * Alpha vs the cross-sectional market factor (equal-weight of all names)

If market-neutral model alpha ~ 0 and random matches it, the pipeline is
CORRECT but the features carry no tradable signal yet. That is the truth.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.models.ml.lightgbm_trainer import LightGBMTrainer
from src.training.walk_forward import WalkForwardCV
from src.backtest.engine import VectorizedBacktester
from src.backtest.costs import IndianCostModel
from src.backtest.stats import deflated_sharpe, market_alpha

DEFAULT_MODEL = PROJECT_ROOT / "models" / "lgbm_5d.joblib"
DEFAULT_FEATURES = PROJECT_ROOT / "data" / "offline" / "features.parquet"


def rank_features(df: pd.DataFrame, feat_cols) -> list[str]:
    rank_cols = []
    for col in feat_cols:
        rcol = f"rank_{col}"
        df[rcol] = df.groupby("event_ts")[col].rank(pct=True, method="average",
                                                     na_option="keep")
        rank_cols.append(rcol)
    return rank_cols


def oos_predictions(df, model_path, feat_cols, target_col, folds, train_days,
                    test_days, gap_days):
    """Walk-forward OOS predictions (leakage-free), returns df with 'prediction'."""
    trainer = LightGBMTrainer.load(str(model_path))
    import lightgbm as lgb

    cv = WalkForwardCV(n_splits=folds, train_size_days=train_days,
                       test_size_days=test_days, gap_days=gap_days, expanding=True)
    df_clean = df.dropna(subset=feat_cols + [target_col]).reset_index(drop=True)
    rows = []
    for _, (tr_i, te_i) in enumerate(cv.split(df_clean)):
        tr_d, te_d = df_clean.iloc[tr_i].copy(), df_clean.iloc[te_i].copy()
        m = lgb.LGBMRegressor(**trainer.model.get_params())
        m.fit(tr_d[feat_cols], tr_d[target_col])
        te_d["prediction"] = m.predict(te_d[feat_cols])
        rows.append(te_d)
    return pd.concat(rows, ignore_index=True)


def run_backtest(bt_df, top_n, hold_days, long_short, label):
    bt = VectorizedBacktester(top_n=top_n, cost_model=IndianCostModel(),
                               hold_days=hold_days, long_short=long_short)
    bt_df = bt_df.copy()
    bt_df["fwd_ret_1d"] = (
        bt_df.groupby("symbol")["close"].shift(-1) / bt_df["close"] - 1.0
    )
    res = bt.run(bt_df[["symbol", "event_ts", "prediction", "close"]],
                 prediction_col="prediction", price_col="close")
    s = res["summary"]
    net = res["daily_returns"]
    # Market factor = equal-weight cross-sectional return each day
    mkt = bt_df.groupby("event_ts")["fwd_ret_1d"].mean()
    mkt = mkt.reindex(net.index)
    ds = deflated_sharpe(net, n_trials=20)
    ma = market_alpha(net, mkt)
    print(f"\n  [{label}]")
    print(f"    net total ret : {s['net_total_return']:+.2%}   Sharpe {s['net_sharpe']:+.3f}")
    print(f"    deflated Sharpe (20 trials): {ds['deflated_sharpe']:+.3f}  "
          f"p(no-edge)={ds['p_value']:.3f}")
    print(f"    alpha(ann)    : {ma['alpha_ann']:+.4f}   beta {ma['beta']:+.3f}  "
          f"R^2(market) {ma['r2']:.3f}")
    return s, ds, ma


def main() -> int:
    ap = argparse.ArgumentParser(description="Artha honest evaluation")
    ap.add_argument("--model", default=str(DEFAULT_MODEL))
    ap.add_argument("--features", default=str(DEFAULT_FEATURES))
    ap.add_argument("--top-n", type=int, default=5)
    ap.add_argument("--hold-days", type=int, default=5)
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--train-days", type=int, default=750)
    ap.add_argument("--test-days", type=int, default=125)
    ap.add_argument("--gap-days", type=int, default=5)
    ap.add_argument("--target", type=str, default="target_fwd_ret_5d",
                    help="Forward-return target column (default: 5d).")
    args = ap.parse_args()

    df = pd.read_parquet(args.features)
    raw = sorted(c for c in df.columns if c.startswith("feat_"))
    rank_cols = rank_features(df, raw)
    target = args.target
    # Default rebalance frequency to the forecast horizon (minimise turnover).
    hold_days = args.hold_days if args.hold_days != 5 else None
    if hold_days is None:
        horizon = int(target.replace("target_fwd_ret_", "").replace("d", ""))
        hold_days = max(1, horizon)

    print(f"\n{'='*64}\n  Artha -- HONEST EVALUATION (alpha vs beta vs random)\n{'='*64}")
    print(f"  {df['symbol'].nunique()} symbols | {len(df):,} rows | "
          f"{df['event_ts'].dt.date.nunique()} days")
    print(f"  Target: {target}  (hold-days = {hold_days})")

    # Model OOS predictions
    model_df = oos_predictions(df, args.model, rank_cols, target, args.folds,
                                args.train_days, args.test_days, args.gap_days)
    # Random null
    rng = np.random.default_rng(7)
    rand_df = model_df.copy()
    rand_df["prediction"] = rng.random(len(rand_df))

    print("\n--- LONG-ONLY (bull-market flattering) ---")
    run_backtest(model_df, args.top_n, hold_days, False, "model long-only")

    print("\n--- MARKET-NEUTRAL (long top-N / short bottom-N) ---")
    s_mod, ds_mod, ma_mod = run_backtest(model_df, args.top_n, hold_days, True,
                                          "model L/S")

    print("\n--- MARKET-NEUTRAL RANDOM (null check) ---")
    s_rnd, ds_rnd, ma_rnd = run_backtest(rand_df, args.top_n, hold_days, True,
                                          "random L/S")

    print("\n" + "=" * 64)
    print("  VERDICT")
    print("=" * 64)
    if ma_mod["alpha_ann"] > 0.02 and abs(ma_mod["alpha_ann"] - ma_rnd["alpha_ann"]) > 0.01:
        print("  [ALPHA] model neutral alpha exceeds random by a real margin.")
    elif ds_mod["p_value"] < 0.05:
        print("  [EDGE] deflated Sharpe significant (p<0.05) -- plausible skill.")
    else:
        print("  [NO ALPHA] neutral model alpha ~ random. Long-only profit is")
        print("  MARKET BETA, not model skill. The features carry no tradable")
        print(f"  {target} signal yet. Next: FII flows, options PCR, sentiment.")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
