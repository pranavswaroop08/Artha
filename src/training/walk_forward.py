"""Walk-forward cross-validation with a purge gap (time-series safe).

Standard K-Fold shuffles rows and leaks future into past. For a forecasting
target with horizon ``h``, the label at day ``T`` depends on prices up to
``T+h``; if the test set starts within ``h`` days of the train set's end, those
future prices leak into training. WalkForwardCV enforces a purge ``gap_days``
between the end of each train window and the start of the test window, and the
gap MUST be >= the forecast horizon.

The splitter works on *dates* (not raw row positions), so multiple symbols
sharing the same trading day are grouped correctly: a given day is either fully
in train, fully in the gap, or fully in test -- never split across.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

import numpy as np
import pandas as pd

from ..common.context import get_logger

logger = get_logger(__name__)


@dataclass
class WalkForwardCV:
    """Rolling walk-forward splitter with a purge gap.

    Args:
        n_splits: number of train/test folds to yield.
        train_size_days: number of distinct trading days per train window.
        test_size_days: number of distinct trading days per test window.
        gap_days: purge gap (distinct days) between train end and test start.
            MUST be >= the forecast horizon to prevent target leakage.
        expanding: if True, the train window grows (anchored start); if False
            (default), it rolls with a fixed size.
    """

    n_splits: int = 5
    train_size_days: int = 60
    test_size_days: int = 20
    gap_days: int = 5
    expanding: bool = False

    def __post_init__(self):
        if self.n_splits < 1:
            raise ValueError("n_splits must be >= 1")
        if self.train_size_days < 1 or self.test_size_days < 1:
            raise ValueError("train_size_days and test_size_days must be >= 1")
        if self.gap_days < 0:
            raise ValueError("gap_days must be >= 0")

    def validate_gap_for_horizon(self, horizon: int) -> None:
        """Fail closed if the purge gap is smaller than the forecast horizon."""
        if self.gap_days < horizon:
            raise ValueError(
                f"gap_days ({self.gap_days}) < forecast horizon ({horizon}): "
                "test targets would leak into training. Increase gap_days."
            )

    def split(
        self, df: pd.DataFrame, time_col: str = "event_ts"
    ) -> Iterator[tuple[np.ndarray, np.ndarray]]:
        """Yield ``(train_idx, test_idx)`` positional index arrays per fold.

        Indices are positions into ``df`` as passed (row order preserved).
        """
        if time_col not in df.columns:
            raise ValueError(f"df must contain time column '{time_col}'")

        ts = pd.to_datetime(df[time_col])
        dates = np.sort(ts.dt.normalize().unique())
        n_dates = len(dates)

        window = self.train_size_days + self.gap_days + self.test_size_days
        if window > n_dates:
            raise ValueError(
                f"Not enough distinct days ({n_dates}) for one fold "
                f"(need train+gap+test = {window})."
            )

        # Step so that n_splits test windows tile the tail of the timeline.
        max_start = n_dates - window
        if self.n_splits == 1:
            starts = [max_start]
        else:
            step = max_start // (self.n_splits - 1) if max_start > 0 else 0
            starts = [i * step for i in range(self.n_splits)]

        ts_norm = ts.dt.normalize()
        for start in starts:
            train_lo = 0 if self.expanding else start
            train_hi = start + self.train_size_days           # exclusive
            test_lo = train_hi + self.gap_days
            test_hi = test_lo + self.test_size_days           # exclusive

            train_dates = set(dates[train_lo:train_hi])
            test_dates = set(dates[test_lo:test_hi])

            train_idx = np.where(ts_norm.isin(train_dates).to_numpy())[0]
            test_idx = np.where(ts_norm.isin(test_dates).to_numpy())[0]
            if len(train_idx) == 0 or len(test_idx) == 0:
                continue
            logger.info(
                "walk_forward_fold",
                train_days=len(train_dates),
                test_days=len(test_dates),
                gap_days=self.gap_days,
            )
            yield train_idx, test_idx
