#!/usr/bin/env python
"""Fetch daily news headlines for the Nifty 50 universe via Google News RSS.

Free, key-less. Outputs data/news_headlines.parquet with columns:
    symbol, fetched_date, headline, source, query

A market-wide feed (query 'Nifty Indian stock market') is stored with
symbol='MARKET' so we can build a broad sentiment regime feature too.

Usage:
    python scripts/fetch_news.py
    python scripts/fetch_news.py --date 2026-07-17 --out data/news_headlines.parquet
"""
from __future__ import annotations

import argparse
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Reuse the Nifty 50 list from ingest_n50.
try:
    from scripts.ingest_n50 import NIFTY_50
except Exception:
    NIFTY_50 = []

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
RSS = "https://news.google.com/rss/search?q={q}&hl=en-IN&gl=IN&ceid=IN:en"


def _fetch(query: str, timeout: int = 20) -> list[dict]:
    url = RSS.format(q=requests.utils.quote(query))
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        rows = []
        for it in root.findall(".//item"):
            title = (it.findtext("title") or "").strip()
            src = (it.findtext("source") or "").strip()
            if title:
                rows.append({"headline": title, "source": src})
        return rows
    except Exception as exc:
        print(f"  [warn] query '{query}' failed: {exc}")
        return []


def main() -> int:
    ap = argparse.ArgumentParser(description="Fetch Nifty 50 news headlines (Google News RSS)")
    ap.add_argument("--date", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    ap.add_argument("--out", default=str(PROJECT_ROOT / "data" / "news_headlines.parquet"))
    ap.add_argument("--limit", type=int, default=20, help="max headlines per query")
    args = ap.parse_args()

    fetched = args.date
    rows: list[dict] = []

    # Market-wide feed first.
    print(f"Fetching MARKET news...")
    for h in _fetch("Nifty Indian stock market sensex"):
        rows.append({"symbol": "MARKET", "fetched_date": fetched,
                     "headline": h["headline"], "source": h["source"]})

    # Per-symbol feeds.
    for sym in NIFTY_50:
        print(f"Fetching {sym} news...")
        got = _fetch(f"{sym} stock NSE")
        for h in got[: args.limit]:
            rows.append({"symbol": sym, "fetched_date": fetched,
                         "headline": h["headline"], "source": h["source"]})
        time.sleep(0.2)  # be polite to the RSS endpoint

    if not rows:
        print("[ERROR] No headlines fetched.")
        return 1

    df = pd.DataFrame(rows)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(args.out, index=False)
    print(f"[OK] {len(df):,} headlines -> {args.out}")
    print(f"  symbols covered: {df['symbol'].nunique()} | date {fetched}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
