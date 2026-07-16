"""Tests for PIT-safe feature engineering."""
from __future__ import annotations

import pandas as pd
import pytest

from src.features.momentum import calculate_momentum_features
from src.features.volatility import calculate_volatility_features
from src.features.volume import calculate_volume_features


@pytest.fixture
def sample_feature_data() -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=25)
    return pd.DataFrame(
        {
            "symbol": ["TEST"] * 25,
            "event_ts": dates,
            "high_adj": [105 + i for i in range(25)],
            "low_adj": [95 + i for i in range(25)],
            "close_adj": [100 + i for i in range(25)],
            "volume_adj": [1000] * 25,
        }
    )


def test_momentum_features(sample_feature_data):
    df = calculate_momentum_features(sample_feature_data)
    assert df["feat_ret_1d"].iloc[1] == pytest.approx(0.01)  # 101/100 - 1
    assert pd.isna(df["feat_rsi_14"].iloc[13])
    assert not pd.isna(df["feat_rsi_14"].iloc[14])
    # PIT: last row must be valid (no forward shift eating the tail).
    assert not pd.isna(df["feat_ret_1d"].iloc[-1])
    assert not pd.isna(df["feat_ret_5d"].iloc[-1])


def test_volatility_features(sample_feature_data):
    df = calculate_volatility_features(sample_feature_data)
    assert pd.isna(df["feat_vol_14d"].iloc[13])
    assert not pd.isna(df["feat_vol_14d"].iloc[14])
    # ATR: TR is valid from row 0 (high-low fallback when no prev close),
    # so ATR(14) is first valid at index 13 (14 TR values), NaN at 12.
    assert pd.isna(df["feat_atr_14"].iloc[12])
    assert not pd.isna(df["feat_atr_14"].iloc[13])


def test_volume_features(sample_feature_data):
    df = calculate_volume_features(sample_feature_data)
    assert pd.isna(df["feat_vol_ma_5"].iloc[3])
    assert not pd.isna(df["feat_vol_ma_5"].iloc[4])
    assert df["feat_vol_ratio_20"].iloc[19] == pytest.approx(1.0)  # 1000 / 1000


def test_features_no_cross_symbol_bleed():
    """A feature at symbol B's first row must NOT use symbol A's tail."""
    dates = pd.date_range("2026-01-01", periods=5)
    df = pd.DataFrame(
        {
            "symbol": ["A"] * 5 + ["B"] * 5,
            "event_ts": list(dates) + list(dates),
            "high_adj": [105] * 10,
            "low_adj": [95] * 10,
            "close_adj": [100, 101, 102, 103, 104, 200, 202, 204, 206, 208],
            "volume_adj": [1000] * 10,
        }
    )
    mom = calculate_momentum_features(df)
    # First row of symbol B (index 5 after stable sort) has no prior B row ->
    # 1d return must be NaN, NOT 200/104-1 (which would be A->B bleed).
    b_first = mom[mom["symbol"] == "B"].iloc[0]
    assert pd.isna(b_first["feat_ret_1d"])
    # Second B row: 202/200 - 1 = 0.01 (within B only).
    b_second = mom[mom["symbol"] == "B"].iloc[1]
    assert b_second["feat_ret_1d"] == pytest.approx(0.01)
