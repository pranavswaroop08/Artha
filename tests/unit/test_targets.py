"""Tests for target variable construction (PIT-safe forward returns)."""
from __future__ import annotations

import pandas as pd
import pytest

from src.data.targets import calculate_forward_returns


@pytest.fixture
def sample_price_data() -> pd.DataFrame:
    """6 days of (assumed adjusted) price data for one symbol."""
    return pd.DataFrame(
        {
            "symbol": ["TEST"] * 6,
            "event_ts": pd.to_datetime(
                ["2026-01-01", "2026-01-02", "2026-01-03",
                 "2026-01-04", "2026-01-05", "2026-01-06"]
            ),
            "close": [100, 110, 105, 115, 120, 125],
        }
    )


def test_forward_return_1d(sample_price_data):
    df = calculate_forward_returns(sample_price_data, horizons=[1])
    val_day1 = df.loc[df["event_ts"] == "2026-01-01", "target_fwd_ret_1d"].iloc[0]
    assert val_day1 == pytest.approx(0.10)  # 110/100 - 1
    val_last = df.loc[df["event_ts"] == "2026-01-06", "target_fwd_ret_1d"].iloc[0]
    assert pd.isna(val_last)  # no day+1 exists


def test_forward_return_5d(sample_price_data):
    df = calculate_forward_returns(sample_price_data, horizons=[5])
    val_day1 = df.loc[df["event_ts"] == "2026-01-01", "target_fwd_ret_5d"].iloc[0]
    assert val_day1 == pytest.approx(0.25)  # 125/100 - 1
    val_day2 = df.loc[df["event_ts"] == "2026-01-02", "target_fwd_ret_5d"].iloc[0]
    assert pd.isna(val_day2)  # 2 + 5 = 7 > 6 -> no future price


def test_missing_columns_raises():
    bad_df = pd.DataFrame({"close": [100, 110]})
    with pytest.raises(ValueError, match="missing required columns"):
        calculate_forward_returns(bad_df, horizons=[1])


def test_missing_price_col_raises(sample_price_data):
    with pytest.raises(ValueError, match="missing required columns"):
        calculate_forward_returns(sample_price_data.drop(columns=["close"]),
                                  horizons=[1], price_col="adj_close")


def test_multisymbol_does_not_bleed():
    """Shift must stay within each symbol; no cross-symbol label bleed."""
    df = pd.DataFrame(
        {
            "symbol": ["A", "A", "B", "B"],
            "event_ts": pd.to_datetime(
                ["2026-01-01", "2026-01-02", "2026-01-01", "2026-01-02"]
            ),
            "close": [100, 110, 200, 180],
        }
    )
    out = calculate_forward_returns(df, horizons=[1])
    # Symbol B, day 2026-01-01: future is 180/200 - 1 = -0.10 (NOT 110/200).
    b_day1 = out.loc[
        (out["symbol"] == "B") & (out["event_ts"] == "2026-01-01"),
        "target_fwd_ret_1d",
    ].iloc[0]
    assert b_day1 == pytest.approx(-0.10)


def test_default_horizons_present(sample_price_data):
    out = calculate_forward_returns(sample_price_data)  # no horizons arg
    for h in (1, 5, 21):
        assert f"target_fwd_ret_{h}d" in out.columns
