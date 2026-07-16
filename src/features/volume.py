"""Volume feature calculations.

PIT-safe: trailing rolling windows only (current bar's volume is known at T).
"""
from __future__ import annotations

import pandas as pd

from ..common.context import get_logger

logger = get_logger(__name__)


def calculate_volume_features(
    df: pd.DataFrame, vol_col: str = "volume_adj"
) -> pd.DataFrame:
    """Volume features. Requires ['symbol', 'event_ts', vol_col]."""
    df_out = df.copy().sort_values(["symbol", "event_ts"]).reset_index(drop=True)
    if vol_col not in df_out.columns:
        vol_col = "volume"

    df_out["feat_vol_ma_5"] = (
        df_out.groupby("symbol")[vol_col]
        .rolling(window=5, min_periods=5)
        .mean()
        .reset_index(level=0, drop=True)
    )
    df_out["feat_vol_ma_20"] = (
        df_out.groupby("symbol")[vol_col]
        .rolling(window=20, min_periods=20)
        .mean()
        .reset_index(level=0, drop=True)
    )
    df_out["feat_vol_ratio_20"] = df_out[vol_col] / df_out["feat_vol_ma_20"]

    logger.info("volume_features", n_rows=len(df_out))
    return df_out
