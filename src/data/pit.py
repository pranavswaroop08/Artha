"""Point-in-Time (PIT) data access utilities.

Rule A of the platform: Every fact carries ``as_of_ts`` (when it became
publicly knowable) and ``event_ts`` (when the underlying event occurred).
Fundamental / earnings / macro data is published with a delay, so it is
invisible to the model before its disclosure timestamp.

These helpers are the hard gate that prevents lookahead bias: a model
querying data at ``current_ts`` can only ever see rows with
``as_of_ts <= current_ts``.
"""
from __future__ import annotations

import pandas as pd
from typing import Optional

from ..common.exceptions import LeakageError

# Backwards/forward-friendly alias so callers/tests can import either name.
FutureLeakError = LeakageError

_AS_OF_COL = "as_of_ts"


def get_pit_dataframe(df: pd.DataFrame, current_ts: pd.Timestamp) -> pd.DataFrame:
    """Filter ``df`` to rows knowable at ``current_ts`` (PIT gate).

    Args:
        df: Input frame that MUST contain an ``as_of_ts`` column.
        current_ts: The timestamp at which the model/agent is querying data.

    Returns:
        Rows where ``as_of_ts <= current_ts`` (copy, fresh index).

    Raises:
        ValueError: if ``as_of_ts`` is missing.
        TypeError: if ``current_ts`` cannot be coerced to a timestamp.
    """
    if _AS_OF_COL not in df.columns:
        raise ValueError("DataFrame must contain 'as_of_ts' column for PIT filtering")

    df = df.copy()
    df[_AS_OF_COL] = pd.to_datetime(df[_AS_OF_COL])
    current_ts = pd.to_datetime(current_ts)
    return df[df[_AS_OF_COL] <= current_ts].reset_index(drop=True)


def assert_no_future_leakage(df: pd.DataFrame, current_ts: pd.Timestamp) -> None:
    """Raise if any row in ``df`` became knowable *after* ``current_ts``.

    Used in CI gates and at live-inference time to fail closed rather than
    silently trade on future information.

    Raises:
        LeakageError (aliased as FutureLeakError): on detected leakage.
    """
    current_ts = pd.to_datetime(current_ts)
    as_of = pd.to_datetime(df[_AS_OF_COL]) if _AS_OF_COL in df.columns else pd.Series([], dtype="datetime64[ns]")
    future = df.loc[as_of > current_ts]
    if not future.empty:
        raise LeakageError(
            f"Future leakage detected! {len(future)} rows have "
            f"{_AS_OF_COL} > {current_ts}."
        )
