#!/usr/bin/env python
"""Turn raw headlines into daily per-symbol + market sentiment features.

Reads data/news_headlines.parquet (symbol, fetched_date, headline, source),
scores each headline with src.nlp.sentiment (local by default; --kimi to use
Kimi LLM), aggregates to daily:
    news_sent_net  : mean headline score per (symbol, date) in [-1, 1]
    news_sent_pos  : fraction of headlines that were positive
    news_sent_neg  : fraction negative
and a market-wide:
    mkt_sent_net    : mean over MARKET headlines that date

Then left-joins these onto the feature frame on (symbol, event_ts.date) and
writes the result. Market sentiment is carried onto EVERY symbol's row for
that day (it's a regime feature, constant-within-day).

Usage:
    python scripts/enrich_sentiment.py --in data/n50_2015/offline/features_2019plus.parquet
    python scripts/enrich_sentiment.py --in ... --kimi   # use Kimi (needs key)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from src.nlp.sentiment import score_headlines


def build_sentiment(news_path: str, provider: str, api_key: str | None) -> pd.DataFrame:
    news = pd.read_parquet(news_path)
    news["fetched_date"] = pd.to_datetime(news["fetched_date"]).dt.normalize()

    # Score all headlines in one batch (kimi is batched internally).
    print(f"Scoring {len(news):,} headlines (provider={provider})...")
    news["score"] = score_headlines(news["headline"].tolist(), provider=provider, api_key=api_key)

    news["pos"] = (news["score"] > 0.05).astype(float)
    news["neg"] = (news["score"] < -0.05).astype(float)

    # Per-symbol daily aggregation.
    per_sym = (
        news[news["symbol"] != "MARKET"]
        .groupby(["symbol", "fetched_date"])
        .agg(news_sent_net=("score", "mean"),
             news_sent_pos=("pos", "mean"),
             news_sent_neg=("neg", "mean"),
             news_n=("score", "size"))
        .reset_index()
    )
    # Market-wide daily.
    mkt = (
        news[news["symbol"] == "MARKET"]
        .groupby("fetched_date")
        .agg(mkt_sent_net=("score", "mean"))
        .reset_index()
    )
    per_sym = per_sym.merge(mkt, on="fetched_date", how="left")
    per_sym = per_sym.rename(columns={"fetched_date": "event_ts"})
    return per_sym


def main() -> int:
    ap = argparse.ArgumentParser(description="Add news-sentiment features")
    ap.add_argument("--in", dest="in_path", required=True)
    ap.add_argument("--news", dest="news_path",
                    default=str(PROJECT_ROOT / "data" / "news_headlines.parquet"))
    ap.add_argument("--out", dest="out_path", default=None)
    ap.add_argument("--provider", choices=["local", "kimi"], default="local")
    ap.add_argument("--api-key", default=None)
    args = ap.parse_args()
    out = args.out_path or args.in_path

    if not Path(args.news_path).exists():
        print(f"[ERROR] News file missing: {args.news_path}. Run scripts/fetch_news.py first.")
        return 1

    sent = build_sentiment(args.news_path, args.provider, args.api_key)

    df = pd.read_parquet(args.in_path)
    df["event_ts"] = pd.to_datetime(df["event_ts"])
    df["_date"] = df["event_ts"].dt.normalize()
    # Drop the join key from the sentiment frame so df's event_ts survives.
    sent_join = sent.rename(columns={"event_ts": "_sent_date"})
    merged = df.merge(
        sent_join, left_on=["symbol", "_date"], right_on=["symbol", "_sent_date"], how="left"
    )
    merged = merged.drop(columns=["_sent_date"], errors="ignore")
    # Forward-fill sentiment within each symbol (a day with no news inherits last).
    fill_cols = ["news_sent_net", "news_sent_pos", "news_sent_neg", "news_n", "mkt_sent_net"]
    for c in fill_cols:
        if c in merged.columns:
            merged[c] = merged.groupby("symbol")[c].ffill()
            merged[c] = merged[c].fillna(0.0)

    # HONESTY GUARD: if the news only covers a single recent date, sentiment
    # is constant across history and carries NO time-varying signal -- it must
    # not be treated as a backtestable feature. Warn loudly; the feature is
    # only valid for LIVE prediction once news is accumulated per day.
    n_news_dates = sent["event_ts"].nunique() if "event_ts" in sent.columns else 1
    if n_news_dates <= 1:
        print(
            "[WARN] News covers only 1 date -- sentiment is CONSTANT across the\n"
            "       whole history and is NOT a valid backtest signal. Use this\n"
            "       model only for LIVE prediction after accumulating daily news.\n"
            "       For honest backtests, train WITHOUT --sentiment."
        )

    merged = merged.drop(columns=["_date"], errors="ignore")
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    merged.to_parquet(out, index=False)
    print(f"[OK] sentiment features merged -> {out} ({len(merged):,} rows)")
    print(f"  new cols: {[c for c in fill_cols if c in merged.columns]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
