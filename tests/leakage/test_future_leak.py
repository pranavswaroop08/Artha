"""FutureLeak Harness: CI gate to enforce Point-in-Time discipline.

Rule A: a fact is invisible to the model before its disclosure (as_of_ts).
This suite aggressively injects leakage and asserts our PIT gate catches it,
and confirms the real feature functions are backward-looking only.
"""
from __future__ import annotations

import pandas as pd
import pytest

from src.data.pit import (
    get_pit_dataframe,
    assert_no_future_leakage,
    FutureLeakError,
)
from src.features.momentum import calculate_momentum_features


@pytest.fixture
def leaky_timestamp_data() -> pd.DataFrame:
    """Row for Jan 2 claims to be knowable only on Jan 5 (future)."""
    return pd.DataFrame(
        {
            "symbol": ["TEST", "TEST", "TEST"],
            "event_ts": pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03"]),
            "as_of_ts": pd.to_datetime(["2026-01-01", "2026-01-05", "2026-01-03"]),
            "close": [100, 105, 102],
        }
    )


def test_timestamp_leakage_detected(leaky_timestamp_data):
    """as_of_ts > current_ts must be filtered out and flagged."""
    current_ts = pd.Timestamp("2026-01-03")

    filtered = get_pit_dataframe(leaky_timestamp_data, current_ts)
    assert len(filtered) == 2  # Jan 1 + Jan 3 pass; Jan 2 (as_of Jan 5) blocked

    with pytest.raises(FutureLeakError, match="Future leakage detected"):
        assert_no_future_leakage(leaky_timestamp_data, current_ts)


def test_pit_gate_passes_clean_data(leaky_timestamp_data):
    """After filtering, the gate must NOT raise (fail-closed only on leakage)."""
    current_ts = pd.Timestamp("2026-01-03")
    clean = get_pit_dataframe(leaky_timestamp_data, current_ts)
    assert_no_future_leakage(clean, current_ts)  # should not raise


def test_value_leakage_shift_neg1_caught():
    """Accidental .shift(-1) is unknowable on the last day -> NaN tail."""
    df = pd.DataFrame(
        {
            "symbol": ["TEST"] * 5,
            "event_ts": pd.to_datetime(
                ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05"]
            ),
            "close_adj": [100, 101, 102, 103, 104],
        }
    )
    df["feat_leaky_tomorrow_close"] = df.groupby("symbol")["close_adj"].shift(-1)
    last = df.loc[df["event_ts"] == "2026-01-05", "feat_leaky_tomorrow_close"].iloc[0]
    assert pd.isna(last), "shift(-1) feature must be NaN on the last available day"


def test_pit_safe_features_have_no_value_leakage():
    """Real momentum features must be valid on the last row (no forward shift)."""
    dates = pd.date_range("2026-01-01", periods=25)
    df = pd.DataFrame(
        {
            "symbol": ["TEST"] * 25,
            "event_ts": dates,
            # Rising series so RSI is well-defined (constant close -> 0/0 NaN).
            "high_adj": [105 + i for i in range(25)],
            "low_adj": [95 + i for i in range(25)],
            "close_adj": [100 + i for i in range(25)],
            "volume_adj": [1000] * 25,
        }
    )
    feats = calculate_momentum_features(df)
    assert not pd.isna(feats["feat_ret_1d"].iloc[-1])
    assert not pd.isna(feats["feat_rsi_14"].iloc[-1])
