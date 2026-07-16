"""Volatility feature calculations.

PIT-safe: trailing rolling windows and prev-close references only (no forward
shift). Uses adjusted high/low/close when present, else raw.
"""
from __future__ import annotations

import pandas as pd

from ..common.context import get_logger

logger = get_logger(__name__)


def calculate_volatility_features(
    df: pd.DataFrame, price_col: str = "close_adj"
) -> pd.DataFrame:
    """Volatility features. Requires ['symbol', 'event_ts', price_col]."""
    if price_col not in df.columns:
        price_col = "close"
    df_out = df.copy().sort_values(["symbol", "event_ts"]).reset_index(drop=True)

    ret_1d = df_out.groupby("symbol")[price_col].pct_change(1)
    df_out["feat_vol_14d"] = (
        ret_1d.groupby(df_out["symbol"])
        .rolling(window=14, min_periods=14)
        .std()
        .reset_index(level=0, drop=True)
    )
    df_out["feat_vol_21d"] = (
        ret_1d.groupby(df_out["symbol"])
        .rolling(window=21, min_periods=21)
        .std()
        .reset_index(level=0, drop=True)
    )

    # ATR(14): True Range vs. previous close, per symbol.
    high = df_out["high_adj"] if "high_adj" in df_out.columns else df_out["high"]
    low = df_out["low_adj"] if "low_adj" in df_out.columns else df_out["low"]
    close_prev = df_out.groupby("symbol")[price_col].shift(1)
    tr = pd.concat(
        [high - low, (high - close_prev).abs(), (low - close_prev).abs()],
        axis=1,
    ).max(axis=1)
    df_out["feat_atr_14"] = (
        tr.groupby(df_out["symbol"])
        .rolling(window=14, min_periods=14)
        .mean()
        .reset_index(level=0, drop=True)
    )

    logger.info("volatility_features", n_rows=len(df_out))
    return df_out
