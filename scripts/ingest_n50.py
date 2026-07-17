#!/usr/bin/env python
"""Ingest the Nifty 50 universe via Yahoo Finance into Artha.

Reuses scripts/ingest.py's pipeline but with the full Nifty 50 constituent
list and a SEPARATE output directory (data/n50) so it never clobbers the
existing 19-name features.parquet. Writes data/n50/offline/features.parquet.

Usage:
    python scripts/ingest_n50.py                 # 2020-01-01 -> today
    python scripts/ingest_n50.py --start 2018-01-01
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Nifty 50 constituents (Yahoo .NS tickers). Kept as a static list; refresh from
# NSE if a name is delisted/replaced. A few ADRs/odd tickers omitted.
NIFTY_50 = [
    "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "HDFC", "ITC",
    "SBIN", "BHARTIARTL", "KOTAKBANK", "LT", "AXISBANK", "ASIANPAINT",
    "MARUTI", "SUNPHARMA", "TATAMOTORS", "TATASTEEL", "BAJFINANCE",
    "HINDUNILVR", "WIPRO", "ONGC", "NTPC", "POWERGRID", "ULTRACEMCO",
    "TITAN", "NESTLEIND", "BAJAJFINSV", "GRASIM", "HCLTECH", "TECHM",
    "INDUSINDBK", "M&M", "DRREDDY", "CIPLA", "EICHERMOT", "COALINDIA",
    "JSWSTEEL", "HEROMOTOCO", "BPCL", "SHREECEM", "BRITANNIA", "SBILIFE",
    "HDFCLIFE", "DIVISLAB", "APOLLOHOSP", "TATACONSUM", "UPL", "ADANIPORTS",
    "BAJAJ-AUTO", "VEDL", "ADANIENT", "WIPRO",
]


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Ingest Nifty 50 into data/n50")
    ap.add_argument("--start", default="2020-01-01")
    ap.add_argument("--end", default=None)
    ap.add_argument("--out-dir", default=str(PROJECT_ROOT / "data" / "n50"))
    args = ap.parse_args()

    cmd = [
        sys.executable, str(PROJECT_ROOT / "scripts" / "ingest.py"),
        "--symbols", *NIFTY_50,
        "--start", args.start,
        "--out-dir", args.out_dir,
    ]
    if args.end:
        cmd += ["--end", args.end]

    print(f"Ingesting {len(NIFTY_50)} Nifty 50 names -> {args.out_dir}")
    return subprocess.call(cmd)


if __name__ == "__main__":
    sys.exit(main())
