"""Tests for walk-forward cross-validation with purge gap."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.training.walk_forward import WalkForwardCV


def _daily_df(n_days: int, symbols=("A",)) -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=n_days, freq="D")
    rows = []
    for s in symbols:
        for d in dates:
            rows.append({"symbol": s, "event_ts": d})
    return pd.DataFrame(rows)


def test_yields_requested_n_splits():
    df = _daily_df(200)
    cv = WalkForwardCV(n_splits=5, train_size_days=60, test_size_days=20, gap_days=5)
    folds = list(cv.split(df))
    assert len(folds) == 5


def test_gap_is_respected_and_no_overlap():
    df = _daily_df(200)
    cv = WalkForwardCV(n_splits=4, train_size_days=60, test_size_days=20, gap_days=5)
    ts = pd.to_datetime(df["event_ts"])
    for train_idx, test_idx in cv.split(df):
        train_max = ts.iloc[train_idx].max()
        test_min = ts.iloc[test_idx].min()
        # Test starts strictly after train ends.
        assert test_min > train_max
        # The purge gap: at least gap_days between last train day and first test day.
        gap = (test_min.normalize() - train_max.normalize()).days
        assert gap >= 5
        # No index appears in both sets.
        assert len(set(train_idx) & set(test_idx)) == 0


def test_splits_move_forward_chronologically():
    df = _daily_df(200)
    cv = WalkForwardCV(n_splits=4, train_size_days=50, test_size_days=20, gap_days=5)
    ts = pd.to_datetime(df["event_ts"])
    prev_test_min = None
    for _, test_idx in cv.split(df):
        test_min = ts.iloc[test_idx].min()
        if prev_test_min is not None:
            assert test_min >= prev_test_min
        prev_test_min = test_min


def test_no_train_date_after_test_start():
    df = _daily_df(200)
    cv = WalkForwardCV(n_splits=3, train_size_days=60, test_size_days=20, gap_days=5)
    ts = pd.to_datetime(df["event_ts"])
    for train_idx, test_idx in cv.split(df):
        assert ts.iloc[train_idx].max() < ts.iloc[test_idx].min()


def test_gap_smaller_than_horizon_raises():
    cv = WalkForwardCV(gap_days=3)
    with pytest.raises(ValueError, match="forecast horizon"):
        cv.validate_gap_for_horizon(5)


def test_gap_ge_horizon_ok():
    cv = WalkForwardCV(gap_days=5)
    cv.validate_gap_for_horizon(5)  # should not raise


def test_multisymbol_days_grouped_not_split():
    """A given trading day must be entirely in train or test, never split."""
    df = _daily_df(200, symbols=("A", "B"))
    cv = WalkForwardCV(n_splits=3, train_size_days=60, test_size_days=20, gap_days=5)
    ts = pd.to_datetime(df["event_ts"]).dt.normalize()
    for train_idx, test_idx in cv.split(df):
        train_days = set(ts.iloc[train_idx])
        test_days = set(ts.iloc[test_idx])
        assert train_days.isdisjoint(test_days)


def test_not_enough_data_raises():
    df = _daily_df(30)
    cv = WalkForwardCV(n_splits=3, train_size_days=60, test_size_days=20, gap_days=5)
    with pytest.raises(ValueError, match="Not enough distinct days"):
        list(cv.split(df))


def test_expanding_train_grows():
    df = _daily_df(200)
    cv = WalkForwardCV(
        n_splits=3, train_size_days=40, test_size_days=20, gap_days=5, expanding=True
    )
    sizes = [len(train_idx) for train_idx, _ in cv.split(df)]
    # Expanding window: later folds have >= earlier train sizes, and at least one grows.
    assert sizes == sorted(sizes)
    assert sizes[-1] > sizes[0]
