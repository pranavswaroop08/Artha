#!/usr/bin/env python
"""Artha Data Ingestion Script — Yahoo Finance → Raw Lake → Features → Feast Parquet.

This is the single entry point to feed REAL market data into the platform.
It runs fully offline (no Docker, no TimescaleDB needed) and produces:

    data/raw_lake/<date>.json        ← immutable, content-hashed raw bars
    data/offline/eod_data.parquet   ← Feast-ready offline store (PIT columns)
    data/offline/features.parquet   ← Momentum + Volatility + Volume features

Usage examples:

    # Ingest last 1 year of data for the default 5-stock universe:
    python scripts/ingest.py

    # Custom symbols + date range:
    python scripts/ingest.py --symbols RELIANCE TCS INFY --start 2023-01-01 --end 2024-12-31

    # Specific exchange suffix (BSE):
    python scripts/ingest.py --symbols 500325 --suffix .BO

    # Dry run (just print what would be fetched, no writes):
    python scripts/ingest.py --dry-run

Requirements (beyond platform deps):
    pip install yfinance
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

# Ensure the project root is on sys.path so `src.*` imports work.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from src.data.collectors.yfinance import YFinanceCollector
from src.data.collectors.yfinance_real import RealYFinanceClient
from src.data.raw_lake import RawLake
from src.data.pit import assert_no_future_leakage
from src.data.targets import calculate_forward_returns
from src.features.momentum import calculate_momentum_features
from src.features.volatility import calculate_volatility_features
from src.features.volume import calculate_volume_features
from src.common.context import get_logger

logger = get_logger("ingest")

DEFAULT_SYMBOLS = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ITC"]
DEFAULT_DAYS_BACK = 365  # 1 year of history by default
OFFLINE_DIR = PROJECT_ROOT / "data" / "offline"
RAW_LAKE_DIR = PROJECT_ROOT / "data" / "raw_lake"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Ingest real NSE/BSE EOD data via Yahoo Finance into Artha.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--symbols", nargs="+", default=DEFAULT_SYMBOLS,
        metavar="SYMBOL",
        help="NSE tickers (e.g. RELIANCE TCS INFY). Default: 5-stock universe.",
    )
    p.add_argument(
        "--start", type=str, default=None,
        metavar="YYYY-MM-DD",
        help="Start date (inclusive). Default: 365 days ago.",
    )
    p.add_argument(
        "--end", type=str, default=None,
        metavar="YYYY-MM-DD",
        help="End date (inclusive). Default: yesterday.",
    )
    p.add_argument(
        "--suffix", type=str, default=".NS",
        choices=[".NS", ".BO"],
        help="Yahoo ticker suffix. .NS = NSE (default), .BO = BSE.",
    )
    p.add_argument(
        "--horizons", nargs="+", type=int, default=[1, 5, 21],
        metavar="N",
        help="Forward-return horizons in trading days (default: 1 5 21).",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Print what would be fetched without writing anything.",
    )
    p.add_argument(
        "--no-features", action="store_true",
        help="Skip feature engineering (raw OHLCV only).",
    )
    return p.parse_args()


def _resolve_dates(start_str: str | None, end_str: str | None) -> tuple[dt.date, dt.date]:
    today = dt.date.today()
    end = dt.date.fromisoformat(end_str) if end_str else today - dt.timedelta(days=1)
    start = (
        dt.date.fromisoformat(start_str)
        if start_str
        else end - dt.timedelta(days=DEFAULT_DAYS_BACK)
    )
    if start > end:
        raise ValueError(f"--start {start} is after --end {end}")
    return start, end


def fetch_symbol(
    symbol: str,
    start: dt.date,
    end: dt.date,
    suffix: str,
    lake: RawLake,
    dry_run: bool,
) -> list[dict]:
    """Fetch one symbol's range and persist to raw lake. Returns list of row dicts."""
    client = RealYFinanceClient(suffix=suffix)
    rows = []

    if dry_run:
        print(f"  [DRY RUN] Would fetch {symbol}{suffix} from {start} to {end}")
        return rows

    logger.info("fetching_symbol", symbol=symbol, start=start.isoformat(), end=end.isoformat())

    # Use the bulk fetch_range for efficiency (one HTTP call per symbol).
    for bar in client.fetch_range(symbol, start, end):
        event_ts = dt.datetime(bar.date.year, bar.date.month, bar.date.day, 15, 30)
        newly_written = lake.put(
            source="yf_eod",
            symbol=bar.symbol,
            as_of=bar.date,
            payload=bar.__dict__,
            event_ts=event_ts,
        )
        rows.append({
            "symbol": bar.symbol,
            "event_ts": pd.Timestamp(event_ts),
            "as_of_ts": pd.Timestamp(event_ts),   # EOD price = public at close
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume,
            "delivery_pct": bar.delivery_pct,
            "_newly_written": newly_written,
        })

    new_count = sum(1 for r in rows if r.pop("_newly_written", False))
    logger.info("symbol_done", symbol=symbol, total_bars=len(rows), new_bars=new_count)
    print(f"  [OK] {symbol}{suffix}: {len(rows)} bars ({new_count} new) [{start} -> {end}]")
    return rows


def build_feature_frame(df: pd.DataFrame, horizons: list[int]) -> pd.DataFrame:
    """Apply all feature families + target construction in order."""
    df = calculate_momentum_features(df)
    df = calculate_volatility_features(df)
    df = calculate_volume_features(df)
    df = calculate_forward_returns(df, horizons=horizons)
    return df


def save_parquet(df: pd.DataFrame, path: Path, name: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    print(f"  [OK] Saved {name}: {len(df):,} rows -> {path}")


def main() -> int:
    args = parse_args()
    start, end = _resolve_dates(args.start, args.end)

    print("\n" + "=" * 56)
    print("  Artha -- Data Ingestion")
    print(f"  Symbols : {args.symbols}")
    print(f"  Range   : {start} -> {end}")
    print(f"  Suffix  : {args.suffix}")
    print(f"  Horizons: {args.horizons}d forward returns")
    print(f"  Dry run : {args.dry_run}")
    print("=" * 56 + "\n")

    if args.dry_run:
        print("[DRY RUN] No data will be written.\n")

    lake = RawLake(root=RAW_LAKE_DIR)
    all_rows: list[dict] = []

    for symbol in args.symbols:
        try:
            rows = fetch_symbol(symbol, start, end, args.suffix, lake, args.dry_run)
            all_rows.extend(rows)
        except Exception as exc:
            print(f"  FAIL {symbol}: {exc}", file=sys.stderr)
            logger.error("symbol_fetch_failed", symbol=symbol, error=str(exc))

    if args.dry_run or not all_rows:
        print("\nDone (dry run or no data fetched).")
        return 0

    print(f"\nBuilding DataFrames ({len(all_rows):,} total bars)...")
    df_raw = pd.DataFrame(all_rows)
    df_raw["event_ts"] = pd.to_datetime(df_raw["event_ts"])
    df_raw["as_of_ts"] = pd.to_datetime(df_raw["as_of_ts"])

    # ── PIT sanity check (Rule A) ──────────────────────────────────────────
    now = pd.Timestamp.now()
    try:
        assert_no_future_leakage(df_raw, current_ts=now)
        print("  [OK] PIT check passed (no future leakage)")
    except Exception as exc:
        print(f"  [FAIL] PIT check FAILED: {exc}", file=sys.stderr)
        return 1

    # ── Save raw EOD Parquet (Feast offline source) ────────────────────────
    save_parquet(df_raw, OFFLINE_DIR / "eod_data.parquet", "EOD raw data (Feast source)")

    # ── Feature engineering ────────────────────────────────────────────────
    if not args.no_features:
        print("\nRunning feature engineering...")
        try:
            df_feat = build_feature_frame(df_raw.copy(), args.horizons)
            save_parquet(df_feat, OFFLINE_DIR / "features.parquet", "Feature frame")
            feat_cols = [c for c in df_feat.columns if c not in df_raw.columns]
            print(f"  [OK] Added {len(feat_cols)} feature columns: {feat_cols}")
        except Exception as exc:
            print(f"  [FAIL] Feature engineering failed: {exc}", file=sys.stderr)
            logger.error("feature_engineering_failed", error=str(exc))
    else:
        print("\nSkipping feature engineering (--no-features).")

    print("\n" + "=" * 56)
    print("  Ingestion complete.")
    print(f"  Raw lake : {RAW_LAKE_DIR}")
    print(f"  Parquet  : {OFFLINE_DIR}")
    print("=" * 56 + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
