#!/usr/bin/env python
"""Enrich the existing feature parquet with FREE market-regime macro series.

The base model failed because price-only momentum/vol/volume features carry no
5-day predictive signal (IC ~ 0, neutral alpha ~ 0). This script adds
cross-sectional market-regime features that cost $0 and need no credentials:

    ^INDIAVIX  India VIX (fear gauge)
    ^NSEI      Nifty 50 index level
    USDINR=X   USD/INR fx
    BZ=F       Brent crude (energy shock proxy)
    GC=F       Gold (risk-off proxy)

These are merged onto every symbol by date (same value across the cross-section
each day) and saved to a new parquet so train.py can be pointed at it via
--features. Pure pandas + yfinance; runs fully offline-of-credentials.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

try:
    import yfinance as yf
except ImportError:
    print("[ERROR] yfinance not installed (pip install yfinance)")
    sys.exit(1)

DEFAULT_IN = PROJECT_ROOT / "data" / "offline" / "features.parquet"
DEFAULT_OUT = PROJECT_ROOT / "data" / "offline" / "features_macro.parquet"

# ticker -> column name we store
MACRO_SERIES = {
    "^INDIAVIX": "vix",
    "^NSEI": "nifty",
    "USDINR=X": "usdinr",
    "BZ=F": "brent",
    "GC=F": "gold",
}


def fetch_macro(start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Return a daily df indexed by event_ts with one column per macro series.

    Returns Close (or the adjusted close) for each ticker over [start, end].
    """
    frames = {}
    for ticker, col in MACRO_SERIES.items():
        print(f"  fetching {ticker} ...", end="", flush=True)
        try:
            df = yf.download(
                ticker, start=start.date().isoformat(),
                end=end.date().isoformat(), auto_adjust=True, progress=False,
            )
            if df.empty:
                print(" EMPTY", flush=True)
                continue
            col_close = "Close" if "Close" in df.columns else df.columns[0]
            s = df[col_close].squeeze()
            s.index = pd.to_datetime(s.index).normalize()
            frames[col] = s
            print(f" {len(s)} rows", flush=True)
        except Exception as exc:
            print(f" FAIL: {exc}", flush=True)
    if not frames:
        print("[ERROR] No macro series downloaded.")
        return pd.DataFrame()
    out = pd.DataFrame(frames)
    out.index.name = "event_ts"
    return out.sort_index()


def main() -> int:
    ap = argparse.ArgumentParser(description="Enrich features.parquet with macro series")
    ap.add_argument("--in", dest="in_path", default=str(DEFAULT_IN))
    ap.add_argument("--out", dest="out_path", default=str(DEFAULT_OUT))
    ap.add_argument("--no-save", action="store_true")
    args = ap.parse_args()

    df = pd.read_parquet(args.in_path)
    df["event_ts"] = pd.to_datetime(df["event_ts"])
    start = df["event_ts"].min()
    end = df["event_ts"].max()
    print(f"\nEnriching {len(df):,} rows ({start.date()} -> {end.date()}) with macro series")

    macro = fetch_macro(start, end)
    if macro.empty:
        return 1

    # Forward-fill macro to align with trading dates (markets close on holidays).
    macro = macro.resample("D").ffill().ffill()
    # Merge on calendar DATE (event_ts in features carries a 15:30 time
    # component from ingest; macro index is midnight -> normalize both).
    df["_date"] = df["event_ts"].dt.normalize()
    macro.index = pd.to_datetime(macro.index).normalize()
    df = df.merge(macro, left_on="_date", right_index=True, how="left")
    df = df.drop(columns=["_date"])

    new_cols = [c for c in MACRO_SERIES.values() if c in df.columns]
    # Add simple derived regime features (relative levels).
    if "vix" in df.columns:
        df["vix_z"] = (df["vix"] - df["vix"].rolling(252, min_periods=30).mean()) / \
                      df["vix"].rolling(252, min_periods=30).std(ddof=0)
    if "nifty" in df.columns:
        df["nifty_ret_5d"] = df.groupby("symbol")["nifty"].transform(
            lambda s: s.pct_change(5))
        df["nifty_ret_21d"] = df.groupby("symbol")["nifty"].transform(
            lambda s: s.pct_change(21))
    print(f"  added columns: {new_cols}")

    # Drop rows where macro is still NaN (e.g. before first macro observation).
    before = len(df)
    df = df.dropna(subset=new_cols)
    print(f"  rows after macro-na drop: {len(df):,} (dropped {before - len(df)})")

    if not args.no_save:
        Path(args.out_path).parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(args.out_path, index=False)
        print(f"  [OK] saved -> {args.out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
