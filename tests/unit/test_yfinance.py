"""Tests for the Yahoo Finance (yfinance) collector.

Mock client: deterministic, no network, no yfinance package needed.
Real client: fetches live RELIANCE.NS; skipped automatically when yfinance is
absent or the network call fails (so CI stays credential-free).
"""
from __future__ import annotations

import datetime as dt

import pytest

from src.data.collectors.yfinance import (
    MockYFinanceClient,
    YFinanceCollector,
)

try:
    import yfinance  # noqa: F401

    _HAVE_YF = True
except ImportError:
    _HAVE_YF = False


def test_mock_fetch_eod_returns_valid_bar():
    bar = MockYFinanceClient().fetch_eod("RELIANCE", dt.date(2026, 7, 1))
    assert bar.symbol == "RELIANCE.NS"
    assert bar.close > 0
    assert bar.high >= bar.low
    assert bar.high >= bar.close >= bar.low


def test_mock_collector_reconciles_and_writes_lake(tmp_path):
    from pathlib import Path

    lake = __import__("src.data.raw_lake", fromlist=["RawLake"]).RawLake(root=Path(tmp_path))
    col = YFinanceCollector(client=MockYFinanceClient(), lake=lake)
    bar = col.collect("TCS", dt.date(2026, 7, 1))
    assert bar.symbol == "TCS.NS"
    # Lake received the record.
    rec = lake.get("yf_eod", bar.symbol, bar.date)
    assert rec is not None
    assert rec["symbol"] == "TCS.NS"


def test_mock_collect_range_skips_weekends():
    bars = list(
        YFinanceCollector(client=MockYFinanceClient()).collect_range(
            "RELIANCE", dt.date(2026, 7, 6), dt.date(2026, 7, 12)
        )
    )
    # 2026-07-06 is a Monday; range spans Mon-Sun -> 5 weekdays.
    assert len(bars) == 5
    assert all(b.high >= b.low for b in bars)


@pytest.mark.skipif(not _HAVE_YF, reason="yfinance not installed")
def test_real_fetch_eod_live():
    pytest.importorskip("yfinance")
    from src.data.collectors.yfinance_real import RealYFinanceClient

    client = RealYFinanceClient()
    bar = client.fetch_eod("RELIANCE", dt.date(2026, 7, 9))
    assert bar.symbol == "RELIANCE"
    assert bar.close > 0
    assert bar.high >= bar.low


@pytest.mark.skipif(not _HAVE_YF, reason="yfinance not installed")
def test_real_collect_range_live_returns_rows():
    pytest.importorskip("yfinance")
    col = YFinanceCollector(provider="yfinance")
    bars = list(col.collect_range("RELIANCE", dt.date(2026, 7, 1), dt.date(2026, 7, 10)))
    assert len(bars) >= 1
    assert all(b.close > 0 for b in bars)
