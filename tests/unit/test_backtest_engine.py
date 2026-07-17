"""Tests for the vectorized backtest engine."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.backtest.engine import VectorizedBacktester
from src.backtest.costs import IndianCostModel


@pytest.fixture
def synthetic_predictions() -> pd.DataFrame:
    """3 days, 3 stocks. Prediction at T is a perfect ranker of the T->T+1 move."""
    return pd.DataFrame({
        "symbol": ["A", "B", "C"] * 3,
        "event_ts": pd.to_datetime(
            ["2026-01-01"] * 3 + ["2026-01-02"] * 3 + ["2026-01-03"] * 3
        ),
        "prediction": [0.10, 0.05, 0.01, 0.20, 0.10, 0.00, 0.30, 0.15, 0.05],
        "close": [100, 100, 100, 110, 105, 101, 132, 115, 101],
    })


def test_backtest_alignment_and_gross_return(synthetic_predictions):
    """Single-shift alignment: pred at T earns close[T+1]/close[T]-1.
    Day1 pred picks A (+10%), Day2 pred picks A (+20%), Day3 dropped."""
    bt = VectorizedBacktester(top_n=1)
    res = bt.run(synthetic_predictions)
    assert res["summary"]["n_days"] == 2
    # Gross = 1.10 * 1.20 - 1 = 0.32 exactly.
    assert res["summary"]["gross_total_return"] == pytest.approx(0.32, abs=1e-9)
    # Day-1 gross return is exactly +10%.
    assert res["gross_daily_returns"].iloc[0] == pytest.approx(0.10, abs=1e-9)


def test_costs_reduce_return_below_gross(synthetic_predictions):
    """Rule B: net must be strictly below gross, by a positive cost drag."""
    bt = VectorizedBacktester(top_n=1)
    res = bt.run(synthetic_predictions)
    s = res["summary"]
    assert s["net_total_return"] < s["gross_total_return"]
    assert s["cost_drag_total"] > 0
    # Net still positive here (signal easily beats cost).
    assert s["net_total_return"] > 0


def test_zero_cost_model_makes_net_equal_gross(synthetic_predictions):
    """With all cost rates zeroed, net == gross (isolates the cost path)."""
    free = IndianCostModel(
        brokerage_pct=0.0, brokerage_cap_inr=0.0, stt_intraday_pct=0.0,
        stt_delivery_pct=0.0, exchange_txn_pct=0.0, sebi_pct=0.0,
        stamp_duty_intraday_pct=0.0, stamp_duty_delivery_pct=0.0,
        gst_pct=0.0, dp_charges_inr=0.0,
    )
    bt = VectorizedBacktester(top_n=1, cost_model=free)
    res = bt.run(synthetic_predictions)
    s = res["summary"]
    assert s["round_trip_cost_pct"] == pytest.approx(0.0, abs=1e-12)
    assert s["net_total_return"] == pytest.approx(s["gross_total_return"], abs=1e-12)


def test_top_n_selects_multiple_names(synthetic_predictions):
    bt = VectorizedBacktester(top_n=2)
    res = bt.run(synthetic_predictions)
    # 2 names/day * 2 tradable days = 4 positions.
    assert res["summary"]["n_positions"] == 4


def test_missing_columns_raises():
    bt = VectorizedBacktester()
    bad = pd.DataFrame({"symbol": ["A"], "event_ts": [pd.Timestamp("2026-01-01")]})
    with pytest.raises(ValueError, match="DataFrame must contain"):
        bt.run(bad)


def test_single_date_raises():
    bt = VectorizedBacktester(top_n=1)
    one_day = pd.DataFrame({
        "symbol": ["A", "B"],
        "event_ts": pd.to_datetime(["2026-01-01", "2026-01-01"]),
        "prediction": [0.1, 0.2],
        "close": [100, 100],
    })
    with pytest.raises(ValueError, match="No tradable rows"):
        bt.run(one_day)


def test_invalid_top_n_raises():
    with pytest.raises(ValueError, match="top_n"):
        VectorizedBacktester(top_n=0)
