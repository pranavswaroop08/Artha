"""Tests for corporate actions collection and price adjustments."""
from __future__ import annotations

import datetime as dt
import pandas as pd
import pytest

from src.data.corporate_actions import CorporateActionsCollector, apply_adjustments


@pytest.fixture
def mock_prices_with_split() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "symbol": ["TEST"] * 5,
            "event_ts": pd.to_datetime(
                ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05"]
            ),
            "open": [100, 100, 50, 50, 50],
            "high": [105, 105, 55, 55, 55],
            "low": [95, 95, 45, 45, 45],
            "close": [100, 100, 50, 50, 50],
            "volume": [1000, 1000, 2000, 2000, 2000],
        }
    )


@pytest.fixture
def mock_actions() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "symbol": "TEST",
                "event_ts": pd.Timestamp("2026-01-03"),
                "as_of_ts": pd.Timestamp("2026-01-02"),
                "action_type": "SPLIT",
                "value": 2.0,
            }
        ]
    )


def test_mock_collector():
    collector = CorporateActionsCollector(provider="mock")
    df = collector.collect("TEST", dt.date(2026, 1, 1), dt.date(2026, 1, 5))
    assert not df.empty
    assert "action_type" in df.columns
    assert df.iloc[0]["value"] == 2.0


def test_apply_adjustments_splits(mock_prices_with_split, mock_actions):
    df_adj = apply_adjustments(mock_prices_with_split, mock_actions)

    pre = df_adj[df_adj["event_ts"] < "2026-01-03"]
    assert pre["close_adj"].iloc[0] == 50.0  # 100 / 2
    assert pre["volume_adj"].iloc[0] == 2000.0  # 1000 * 2

    post = df_adj[df_adj["event_ts"] >= "2026-01-03"]
    assert post["close_adj"].iloc[0] == 50.0
    assert post["volume_adj"].iloc[0] == 2000.0


def test_collector_invalid_provider():
    with pytest.raises(ValueError, match="Unknown corporate actions provider"):
        CorporateActionsCollector(provider="invalid")


def test_apply_adjustments_dividend():
    prices = pd.DataFrame(
        {
            "event_ts": pd.to_datetime(["2026-02-01", "2026-02-02", "2026-02-03"]),
            "open": [100, 100, 100],
            "high": [105, 105, 105],
            "low": [95, 95, 95],
            "close": [100, 100, 100],
            "volume": [1000, 1000, 1000],
        }
    )
    # 1.0 per share dividend on Feb 2 -> pre-ex close should drop by 1%.
    actions = pd.DataFrame(
        [
            {
                "symbol": "TEST",
                "event_ts": pd.Timestamp("2026-02-02"),
                "as_of_ts": pd.Timestamp("2026-02-01"),
                "action_type": "DIVIDEND",
                "value": 1.0,
            }
        ]
    )
    adj = apply_adjustments(prices, actions)
    assert adj.loc[0, "close_adj"] == pytest.approx(99.0)  # 100 * (1 - 1/100)
    assert adj.loc[2, "close_adj"] == 100.0  # on/after ex-date unchanged


def test_apply_adjustments_multiple_splits_cumulative():
    prices = pd.DataFrame(
        {
            "event_ts": pd.to_datetime(
                ["2026-03-01", "2026-03-02", "2026-03-03", "2026-03-04"]
            ),
            "open": [400, 200, 100, 100],
            "high": [400, 200, 100, 100],
            "low": [400, 200, 100, 100],
            "close": [400, 200, 100, 100],
            "volume": [100, 200, 400, 400],
        }
    )
    actions = pd.DataFrame(
        [
            {
                "symbol": "TEST",
                "event_ts": pd.Timestamp("2026-03-02"),
                "as_of_ts": pd.Timestamp("2026-03-01"),
                "action_type": "SPLIT",
                "value": 2.0,
            },
            {
                "symbol": "TEST",
                "event_ts": pd.Timestamp("2026-03-03"),
                "as_of_ts": pd.Timestamp("2026-03-02"),
                "action_type": "SPLIT",
                "value": 2.0,
            },
        ]
    )
    adj = apply_adjustments(prices, actions)
    # Day 1 (pre both splits) close 400 -> /4 = 100
    assert adj.loc[0, "close_adj"] == pytest.approx(100.0)
    # Day 2 (pre second split) close 200 -> /2 = 100
    assert adj.loc[1, "close_adj"] == pytest.approx(100.0)
    # Day 3+ unchanged
    assert adj.loc[2, "close_adj"] == 100.0
