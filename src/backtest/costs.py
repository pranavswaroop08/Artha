"""Indian Market Trading Cost Model.

Rule B: costs are first-class. A signal that dies after costs is not a signal.
This module is standalone so both the backtest engine and live inference can
subtract identical costs (train/serve parity).

Components: brokerage (capped), STT (intraday sell / delivery both sides),
exchange transaction charges, SEBI turnover fee, stamp duty (buy side),
GST (18% on brokerage + exchange + SEBI), DP charges (delivery sell), and a
simple linear market-impact slippage model based on volume participation.

NOTE: default rates approximate a discount-broker + current regulatory
schedule; they are configurable via the constructor so they can be tuned or
updated as regulations change.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..common.context import get_logger

logger = get_logger(__name__)


@dataclass
class TradeCostBreakdown:
    absolute_cost_inr: float
    percentage_cost_bps: float  # basis points (1 bps = 0.01%)


class IndianCostModel:
    """Transaction costs for NSE/BSE equities."""

    def __init__(
        self,
        brokerage_pct: float = 0.0003,          # 0.03%
        brokerage_cap_inr: float = 20.0,
        stt_intraday_pct: float = 0.00025,      # 0.025% on sell side
        stt_delivery_pct: float = 0.001,        # 0.1% on both sides
        exchange_txn_pct: float = 0.0000325,    # NSE ~0.00325%
        sebi_pct: float = 0.000001,             # Rs.10 per crore
        stamp_duty_intraday_pct: float = 0.00003,   # 0.003% buy side
        stamp_duty_delivery_pct: float = 0.00015,   # 0.015% buy side
        gst_pct: float = 0.18,
        dp_charges_inr: float = 13.5,
        slippage_bps_per_pct_adv: float = 10.0,  # 10 bps per 1% of ADV
        slippage_cap_bps: float = 50.0,
    ):
        self.brokerage_pct = brokerage_pct
        self.brokerage_cap_inr = brokerage_cap_inr
        self.stt_intraday_pct = stt_intraday_pct
        self.stt_delivery_pct = stt_delivery_pct
        self.exchange_txn_pct = exchange_txn_pct
        self.sebi_pct = sebi_pct
        self.stamp_duty_intraday_pct = stamp_duty_intraday_pct
        self.stamp_duty_delivery_pct = stamp_duty_delivery_pct
        self.gst_pct = gst_pct
        self.dp_charges_inr = dp_charges_inr
        self.slippage_bps_per_pct_adv = slippage_bps_per_pct_adv
        self.slippage_cap_bps = slippage_cap_bps

    def calculate_costs(
        self,
        turnover_inr: float,
        is_intraday: bool,
        is_buy: bool,
        order_qty: int = 0,
        daily_volume: int = 1,
    ) -> TradeCostBreakdown:
        """Return absolute (INR) and relative (bps) cost of one order leg."""
        if turnover_inr < 0:
            raise ValueError("Turnover cannot be negative")
        if turnover_inr == 0:
            return TradeCostBreakdown(0.0, 0.0)

        # 1. Brokerage (capped per order)
        brokerage = min(turnover_inr * self.brokerage_pct, self.brokerage_cap_inr)

        # 2. STT: intraday -> sell side only; delivery -> both sides
        if is_intraday:
            stt = 0.0 if is_buy else turnover_inr * self.stt_intraday_pct
        else:
            stt = turnover_inr * self.stt_delivery_pct

        # 3. Exchange transaction charges
        exchange_txn = turnover_inr * self.exchange_txn_pct

        # 4. SEBI turnover fee
        sebi = turnover_inr * self.sebi_pct

        # 5. Stamp duty (buy side only)
        if is_buy:
            rate = (
                self.stamp_duty_intraday_pct
                if is_intraday
                else self.stamp_duty_delivery_pct
            )
            stamp_duty = turnover_inr * rate
        else:
            stamp_duty = 0.0

        # 6. GST (18% on brokerage + exchange + SEBI)
        gst = (brokerage + exchange_txn + sebi) * self.gst_pct

        # 7. DP charges (delivery sell side only) + GST on it
        dp_charges = self.dp_charges_inr if (not is_intraday and not is_buy) else 0.0
        dp_charges_gst = dp_charges * self.gst_pct

        # 8. Slippage (linear market impact vs. ADV participation)
        participation = order_qty / daily_volume if daily_volume > 0 else 1.0
        slippage_bps = min(
            self.slippage_cap_bps,
            self.slippage_bps_per_pct_adv * participation * 100.0,
        )
        slippage_cost = turnover_inr * (slippage_bps / 10000.0)

        total = (
            brokerage + stt + exchange_txn + sebi + stamp_duty
            + gst + dp_charges + dp_charges_gst + slippage_cost
        )
        total_bps = (total / turnover_inr) * 10000.0
        return TradeCostBreakdown(
            absolute_cost_inr=total,
            percentage_cost_bps=total_bps,
        )
