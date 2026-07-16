"""Momentum feature calculations.

PIT-safe: every feature at event_ts=T uses only data with event_ts <= T
(pct_change / diff / trailing rolling windows). No forward shifts.
"""
from __future__ import annotations

import pandas as pd

from ..common.context import get_logger

logger = get_logger(__name__)


def calculate_momentum_features(
    df: pd.DataFrame, price_col: str = "close_adj"
) -> pd.DataFrame:
    """Momentum features. Requires ['symbol', 'event_ts', price_col]."""
    if price_col not in df.columns:
        price_col = "close"
    df_out = df.copy().sort_values(["symbol", "event_ts"]).reset_index(drop=True)

    g = df_out.groupby("symbol")[price_col]
    df_out["feat_ret_1d"] = g.pct_change(1)
    df_out["feat_ret_5d"] = g.pct_change(5)
    df_out["feat_ret_21d"] = g.pct_change(21)

    # RSI(14), Wilder-approximated with a simple rolling mean of gains/losses.
    delta = df_out.groupby("symbol")[price_col].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = (
        gain.groupby(df_out["symbol"])
        .rolling(window=14, min_periods=14)
        .mean()
        .reset_index(level=0, drop=True)
    )
    avg_loss = (
        loss.groupby(df_out["symbol"])
        .rolling(window=14, min_periods=14)
        .mean()
        .reset_index(level=0, drop=True)
    )
    rs = avg_gain / avg_loss
    df_out["feat_rsi_14"] = 100 - (100 / (1 + rs))

    logger.info("momentum_features", n_rows=len(df_out))
    return df_out
