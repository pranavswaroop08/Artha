#!/usr/bin/env python
"""Enrich features with cross-sectional BREADTH / market-internals features.

Breadth is one of the strongest FREE market-internal signals for monthly
direction: when most of the index is above its own moving average, momentum
carries; when breadth collapses, reversals follow. Computed entirely from the
universe's own daily returns -- no external data, no credentials.

Features added (constant-within-day, merged onto every symbol):
    breadth_above_ma50   : fraction of names with close > 50d MA
    breadth_above_ma20   : fraction of names with close > 20d MA
    adv_decay_10         : 10d advance-decline line change
    avg_cross_ret_21d    : equal-weight cross-sectional mean 21d fwd ret proxy
                           (uses same-day 21d PAST return as a regime proxy)

Usage:
    python scripts/enrich_breadth.py --in data/n50/offline/features.parquet
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
import pandas as pd


def add_breadth(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["event_ts", "symbol"]).copy()
    df["_date"] = df["event_ts"].dt.normalize()

    # Per-symbol moving averages of close.
    ma20 = df.groupby("symbol")["close"].transform(lambda s: s.rolling(20, min_periods=10).mean())
    ma50 = df.groupby("symbol")["close"].transform(lambda s: s.rolling(50, min_periods=20).mean())
    above20 = (df["close"] > ma20).astype(float)
    above50 = (df["close"] > ma50).astype(float)

    # Breadth = daily cross-sectional mean of "above MA".
    br20 = above20.groupby(df["_date"]).transform("mean")
    br50 = above50.groupby(df["_date"]).transform("mean")
    df["breadth_above_ma20"] = br20
    df["breadth_above_ma50"] = br50

    # Advance-decline line: daily count up vs down, cumulative.
    up = (df.groupby("symbol")["close"].diff() > 0).astype(float)
    adv = up.groupby(df["_date"]).transform("sum")
    dec = (df.groupby("symbol")["close"].diff() < 0).astype(float)
    dcl = dec.groupby(df["_date"]).transform("sum")
    ad_line = (adv - dcl)
    df["adv_decay_10"] = ad_line.groupby(df["_date"]).transform(
        lambda s: s.rolling(10, min_periods=3).sum())

    # Equal-weight cross-sectional mean 21d PAST return (regime proxy).
    past21 = df.groupby("symbol")["close"].transform(lambda s: s.pct_change(21))
    df["avg_cross_ret_21d"] = past21.groupby(df["_date"]).transform("mean")

    df = df.drop(columns=["_date"])
    return df


def main() -> int:
    ap = argparse.ArgumentParser(description="Add breadth/market-internals features")
    ap.add_argument("--in", dest="in_path", required=True)
    ap.add_argument("--out", dest="out_path", default=None)
    args = ap.parse_args()
    out = args.out_path or args.in_path

    df = pd.read_parquet(args.in_path)
    df["event_ts"] = pd.to_datetime(df["event_ts"])
    before = len(df)
    df = add_breadth(df)
    new = [c for c in ["breadth_above_ma20", "breadth_above_ma50",
                       "adv_decay_10", "avg_cross_ret_21d"] if c in df.columns]
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    print(f"[OK] added breadth features {new} -> {out} ({before:,} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
