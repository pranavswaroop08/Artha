"""Target variable construction for forecasting.

The target is, by definition, a FUTURE event. We compute it from prices and
then *shift it backward* so that the label for prediction time ``T`` equals
the outcome observed ``h`` days later — i.e. the value sits on row ``T``, not
on the future row. This keeps labels aligned with ``event_ts`` for the PIT
layer (pit.get_pit_dataframe) and the Feast point-in-time join.

    target(T, h) = price[T + h] / price[T] - 1

PIT note: because the label is just a shifted transform of the price series,
no future information leaks into row T *as long as* ``price_col`` is the
corporate-action-ADJUSTED price. Using raw ``close`` pollutes returns on
ex-dividend / split dates (the price drops mechanically, not from trading).
"""
from __future__ import annotations

from typing import Optional, List

import pandas as pd

from ..common.context import get_logger

logger = get_logger(__name__)

_DEFAULT_HORIZONS: List[int] = [1, 5, 21]


def calculate_forward_returns(
    df: pd.DataFrame,
    horizons: Optional[List[int]] = None,
    price_col: str = "close",
) -> pd.DataFrame:
    """Compute forward returns and align them to ``event_ts`` (PIT-safe).

    WARNING: ``price_col`` MUST be corporate-action-adjusted (e.g. ``adj_close``).
    Unadjusted ``close`` produces false signals / leakage-looking jumps on
    ex-dividend and split dates. The corporate-actions adjustment module
    (``src/data/corporate_actions.py``) is the upstream dependency that
    produces the adjusted series.

    Args:
        df: Frame sorted (or sortable) by symbol + event_ts. Must contain
            ``symbol``, ``event_ts``, and ``price_col``.
        horizons: Integer day-horizons, e.g. [1, 5, 21]. Defaults to [1, 5, 21].
        price_col: Adjusted price column to use.

    Returns:
        Copy of ``df`` with added ``target_fwd_ret_{h}d`` columns (NaN where the
        future price is unavailable, i.e. the tail of each symbol's series).

    Raises:
        ValueError: if required columns are missing.
    """
    horizons = horizons or list(_DEFAULT_HORIZONS)
    missing = [c for c in ("symbol", "event_ts", price_col) if c not in df.columns]
    if missing:
        raise ValueError(f"DataFrame missing required columns: {missing}")

    df_out = df.copy()
    df_out = df_out.sort_values(["symbol", "event_ts"]).reset_index(drop=True)

    for h in horizons:
        target_col = f"target_fwd_ret_{h}d"
        # shift(-h) brings the FUTURE price onto the CURRENT row, so the label
        # for event_ts=T is the realized return h sessions later. groupby keeps
        # the shift within each symbol (no cross-symbol bleed).
        df_out[target_col] = df_out.groupby("symbol")[price_col].transform(
            lambda x: x.shift(-h) / x - 1
        )
        n_nan = int(df_out[target_col].isna().sum())
        logger.info(
            "forward_return_target", target_col=target_col,
            horizon=h, n_nan_tail=n_nan,
        )
    return df_out
