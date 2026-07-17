#!/usr/bin/env python
"""Artha Backtest Script — model predictions -> cost-adjusted PnL.

Loads the trained model bundle, generates OOS predictions on the full feature
frame using the same walk-forward windows as training, then runs the
VectorizedBacktester with IndianCostModel to produce gross/net Sharpe,
drawdown, and cost drag.

Usage:
    python scripts/backtest.py
    python scripts/backtest.py --model models/lgbm_5d.joblib --top-n 5
    python scripts/backtest.py --top-n 3 --notional 500000
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
from src.backtest.engine import VectorizedBacktester
from src.backtest.costs import IndianCostModel
from src.common.context import get_logger

logger = get_logger("backtest")

DEFAULT_MODEL    = PROJECT_ROOT / "models" / "lgbm_5d.joblib"
DEFAULT_FEATURES = PROJECT_ROOT / "data" / "offline" / "features.parquet"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Backtest Artha LightGBM model.")
    p.add_argument("--model", type=str, default=str(DEFAULT_MODEL))
    p.add_argument("--features", type=str, default=str(DEFAULT_FEATURES))
    p.add_argument("--top-n", type=int, default=5,
                   help="Long top-N stocks per day (default: 5).")
    p.add_argument("--notional", type=float, default=100_000.0,
                   help="Per-leg notional in INR for cost calc (default: 100,000).")
    p.add_argument("--hold-days", type=int, default=5,
                   help="Rebalance every N days (default: 5 = matches 5d forecast horizon).")
    p.add_argument("--folds", type=int, default=5)
    p.add_argument("--train-days", type=int, default=750)
    p.add_argument("--test-days", type=int, default=125)
    p.add_argument("--gap-days", type=int, default=5)
    return p.parse_args()


def add_cs_rank_features(df: pd.DataFrame, feat_cols: list[str]) -> tuple[pd.DataFrame, list[str]]:
    rank_cols = []
    for col in feat_cols:
        rcol = f"rank_{col}"
        df[rcol] = (
            df.groupby("event_ts")[col]
            .rank(pct=True, method="average", na_option="keep")
        )
        rank_cols.append(rcol)
    return df, rank_cols


def annualised_return(daily: pd.Series, trading_days: int = 252) -> float:
    if daily.empty:
        return float("nan")
    cum = (1 + daily).prod()
    n = len(daily)
    return float(cum ** (trading_days / n) - 1)


def main() -> int:
    args = parse_args()

    model_path = Path(args.model)
    feat_path  = Path(args.features)

    for p, label in [(model_path, "Model"), (feat_path, "Features")]:
        if not p.exists():
            print(f"[ERROR] {label} not found: {p}")
            return 1

    print(f"\n{'='*62}")
    print("  Artha -- Backtest")
    print(f"{'='*62}")
    print(f"  Model    : {model_path.name}")
    print(f"  Features : {feat_path.name}")
    print(f"  Top-N    : {args.top_n} stocks per day (equal weight)")
    print(f"  Hold     : every {args.hold_days} days (rebalance frequency)")
    print(f"  Notional : INR {args.notional:,.0f} per leg")
    print()

    # ── Load data & re-generate rank features ─────────────────────────────
    df = pd.read_parquet(feat_path)
    raw_feat_cols = sorted(c for c in df.columns if c.startswith("feat_"))
    df, rank_cols = add_cs_rank_features(df, raw_feat_cols)

    # ── Generate walk-forward OOS predictions ─────────────────────────────
    trainer = LightGBMTrainer.load(str(model_path))
    feat_cols = trainer.feature_cols
    target_col = trainer.target_col

    print(f"  Target   : {target_col}")
    print(f"  Features : {feat_cols}")
    print()

    # Re-run walk-forward to get predictions aligned to test folds
    cv = WalkForwardCV(
        n_splits=args.folds,
        train_size_days=args.train_days,
        test_size_days=args.test_days,
        gap_days=args.gap_days,
        expanding=True,
    )

    df_clean = df.dropna(subset=feat_cols + [target_col]).reset_index(drop=True)
    all_test_rows = []

    print("Generating OOS predictions per fold...")
    for i, (train_idx, test_idx) in enumerate(cv.split(df_clean)):
        train_df = df_clean.iloc[train_idx]
        test_df  = df_clean.iloc[test_idx].copy()

        import lightgbm as lgb
        model = lgb.LGBMRegressor(
            **{k: v for k, v in trainer.model.get_params().items()},
        )
        model.fit(train_df[feat_cols], train_df[target_col])
        test_df["prediction"] = model.predict(test_df[feat_cols])
        all_test_rows.append(test_df)
        print(f"  Fold {i+1}: {len(test_df):,} test rows, "
              f"dates {test_df['event_ts'].dt.date.min()} -> {test_df['event_ts'].dt.date.max()}")

    bt_df = pd.concat(all_test_rows, ignore_index=True)
    print(f"\nTotal backtest rows: {len(bt_df):,} across {bt_df['event_ts'].dt.date.nunique()} days")

    # ── Run backtest ───────────────────────────────────────────────────────
    cost_model = IndianCostModel()
    backtester = VectorizedBacktester(
        top_n=args.top_n,
        cost_model=cost_model,
        notional_per_leg_inr=args.notional,
        hold_days=args.hold_days,
    )

    result = backtester.run(bt_df, prediction_col="prediction", price_col="close")
    summary = result["summary"]
    net_daily: pd.Series = result["daily_returns"]
    gross_daily: pd.Series = result["gross_daily_returns"]

    # ── Extra stats ────────────────────────────────────────────────────────
    ann_gross = annualised_return(gross_daily)
    ann_net   = annualised_return(net_daily)
    win_rate  = float((net_daily > 0).mean())

    # ── Print results ──────────────────────────────────────────────────────
    print()
    print(f"{'='*62}")
    print("  BACKTEST RESULTS  (walk-forward OOS, delivery cost)")
    print(f"{'='*62}")
    print(f"  Trading days            : {summary['n_days']}")
    print(f"  Total positions         : {summary['n_positions']:,}")
    print()
    print(f"  Gross total return      : {summary['gross_total_return']:+.2%}")
    print(f"  Net total return        : {summary['net_total_return']:+.2%}")
    print(f"  Annualised gross return : {ann_gross:+.2%}")
    print(f"  Annualised net return   : {ann_net:+.2%}")
    print()
    print(f"  Gross Sharpe            : {summary['gross_sharpe']:+.3f}")
    print(f"  Net Sharpe              : {summary['net_sharpe']:+.3f}   (target: >0.5)")
    print(f"  Max drawdown            : {summary['max_drawdown']:+.2%}  (limit: -15%)")
    print()
    print(f"  Cost drag (total)       : {summary['cost_drag_total']:+.4%}")
    print(f"  Round-trip cost/name    : {summary['round_trip_cost_pct']*100:.3f}%  ({summary['round_trip_cost_pct']*10000:.1f} bps)")
    print(f"  Win rate (net daily)    : {win_rate:.1%}")
    print(f"{'='*62}")

    # ── Verdict ────────────────────────────────────────────────────────────
    print()
    ns = summary["net_sharpe"]
    md = summary["max_drawdown"]

    if ns >= 0.5 and md >= -0.15:
        print("[PASS]  Net Sharpe >= 0.5 and drawdown within -15%. Signal survives costs.")
    elif ns >= 0.0:
        print(f"[MARGINAL]  Net Sharpe {ns:.3f} -- positive but below 0.5 threshold.")
        print("  Options: more symbols, more features (FII, options PCR), longer history.")
    else:
        print(f"[FAIL]  Net Sharpe {ns:.3f} -- signal does not survive Indian trading costs.")
        print("  This is the expected outcome at this stage (3 price-only features,")
        print("  no macro/options/FII signals). The model structure is correct;")
        print("  alpha needs richer features.")

    print()
    print("  Next: add fundamental + FII + options features to improve IC.")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
