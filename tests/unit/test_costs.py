"""Tests for the Indian trading cost model."""
from __future__ import annotations

import pytest

from src.backtest.costs import IndianCostModel


@pytest.fixture
def cost_model():
    return IndianCostModel()


def test_intraday_buy_cost(cost_model):
    result = cost_model.calculate_costs(
        turnover_inr=100000, is_intraday=True, is_buy=True,
        order_qty=1000, daily_volume=1000000,
    )
    assert result.percentage_cost_bps > 0
    assert result.absolute_cost_inr > 0


def test_intraday_sell_more_expensive_than_buy(cost_model):
    buy = cost_model.calculate_costs(100000, True, True)
    sell = cost_model.calculate_costs(100000, True, False)
    # Sell has STT (intraday sell side); buy does not.
    assert sell.absolute_cost_inr > buy.absolute_cost_inr


def test_delivery_sell_has_dp_charges(cost_model):
    buy = cost_model.calculate_costs(100000, False, True)
    sell = cost_model.calculate_costs(100000, False, False)
    assert sell.absolute_cost_inr > buy.absolute_cost_inr


def test_slippage_scales_with_volume(cost_model):
    small = cost_model.calculate_costs(10000, True, True, order_qty=100, daily_volume=1000000)
    large = cost_model.calculate_costs(1000000, True, True, order_qty=100000, daily_volume=1000000)
    assert large.percentage_cost_bps > small.percentage_cost_bps * 5


def test_brokerage_cap_applied(cost_model):
    # 1 Cr turnover: 0.03% = 3000 uncapped, but cap is 20.
    result = cost_model.calculate_costs(10000000, False, True)
    assert result.percentage_cost_bps < 15


def test_negative_turnover_raises(cost_model):
    with pytest.raises(ValueError, match="Turnover cannot be negative"):
        cost_model.calculate_costs(-1, True, True)


def test_intraday_buy_exact_math(cost_model):
    """Exact component math for an intraday BUY, tiny participation (~0 slippage)."""
    turnover = 100000.0
    r = cost_model.calculate_costs(turnover, is_intraday=True, is_buy=True,
                                   order_qty=1, daily_volume=10**9)
    brokerage = min(turnover * 0.0003, 20.0)          # 20 (capped: 30 -> 20)
    stt = 0.0                                          # intraday buy -> no STT
    exch = turnover * 0.0000325                        # 3.25
    sebi = turnover * 0.000001                         # 0.1
    stamp = turnover * 0.00003                         # 3.0 (intraday buy)
    gst = (brokerage + exch + sebi) * 0.18            # (20+3.25+0.1)*0.18
    expected = brokerage + stt + exch + sebi + stamp + gst  # slippage ~0
    assert r.absolute_cost_inr == pytest.approx(expected, abs=0.05)


def test_delivery_sell_exact_dp_and_stt(cost_model):
    """Delivery SELL: STT 0.1% both sides + DP charge 13.5 + GST on DP."""
    turnover = 100000.0
    r = cost_model.calculate_costs(turnover, is_intraday=False, is_buy=False,
                                   order_qty=1, daily_volume=10**9)
    brokerage = min(turnover * 0.0003, 20.0)          # 20
    stt = turnover * 0.001                             # 100 (delivery)
    exch = turnover * 0.0000325                        # 3.25
    sebi = turnover * 0.000001                         # 0.1
    stamp = 0.0                                        # sell -> no stamp
    gst = (brokerage + exch + sebi) * 0.18
    dp = 13.5
    dp_gst = dp * 0.18
    expected = brokerage + stt + exch + sebi + stamp + gst + dp + dp_gst
    assert r.absolute_cost_inr == pytest.approx(expected, abs=0.05)
