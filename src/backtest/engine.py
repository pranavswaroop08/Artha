"""Vectorized long-only backtest engine with Indian-cost overlay.

Alignment (PIT-safe, single shift): a prediction made at ``event_ts = T`` is
traded at the next bar and earns the return ``close[T+1]/close[T] - 1``. We
compute the forward 1-day return per symbol and pair it with the CURRENT-row
prediction; the last bar of each symbol has no forward return and is dropped.
There is NO second shift of the prediction -- doing both (lag pred AND lead
return) opens a 2-day gap and is a bug.

Costs: turnover-based. A daily-rebalanced top-N book buys and sells each name,
so per-name round-trip cost = (buy_bps + sell_bps) scaled by weight. Delivery
cost schedule is used (overnight hold) via IndianCostModel.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from .costs import IndianCostModel
from ..common.context import get_logger

logger = get_logger(__name__)

TRADING_DAYS = 252


class VectorizedBacktester:
    def __init__(
        self,
        top_n: int = 5,
        cost_model: Optional[IndianCostModel] = None,
        notional_per_leg_inr: float = 100_000.0,
    ):
        if top_n < 1:
            raise ValueError("top_n must be >= 1")
        self.top_n = top_n
        self.cost_model = cost_model or IndianCostModel()
        self.notional_per_leg_inr = notional_per_leg_inr

    def _round_trip_cost_pct(self) -> float:
        """Buy + sell delivery cost as a fraction of traded notional (per name)."""
        buy = self.cost_model.calculate_costs(
            turnover_inr=self.notional_per_leg_inr, is_intraday=False, is_buy=True
        ).percentage_cost_bps
        sell = self.cost_model.calculate_costs(
            turnover_inr=self.notional_per_leg_inr, is_intraday=False, is_buy=False
        ).percentage_cost_bps
        return (buy + sell) / 10_000.0

    def run(
        self,
        df: pd.DataFrame,
        prediction_col: str = "prediction",
        price_col: str = "close",
    ) -> Dict[str, Any]:
        required = ["event_ts", "symbol", prediction_col, price_col]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"DataFrame must contain {required} (missing {missing})")

        df = df.sort_values(["symbol", "event_ts"]).copy()

        # Forward 1-day return: return from THIS bar's close to the NEXT bar's close.
        df["fwd_ret_1d"] = (
            df.groupby("symbol")[price_col].shift(-1) / df[price_col] - 1.0
        )
        # Pair with the CURRENT prediction (single alignment). Drop last bar/symbol.
        df = df.dropna(subset=[prediction_col, "fwd_ret_1d"])
        if df.empty:
            raise ValueError("No tradable rows after alignment; need >=2 dates.")

        # Daily top-N long book, equal weight.
        df["rank"] = df.groupby("event_ts")[prediction_col].rank(
            ascending=False, method="first"
        )
        book = df[df["rank"] <= self.top_n].copy()
        book["weight"] = 1.0 / self.top_n
        book["gross_ret"] = book["weight"] * book["fwd_ret_1d"]

        # Cost drag: round-trip cost per name, scaled by its weight.
        cost_pct = self._round_trip_cost_pct()
        book["cost_drag"] = book["weight"] * cost_pct
        book["net_ret"] = book["gross_ret"] - book["cost_drag"]

        gross_daily = book.groupby("event_ts")["gross_ret"].sum()
        net_daily = book.groupby("event_ts")["net_ret"].sum()

        summary = {
            "gross_total_return": float((1 + gross_daily).prod() - 1),
            "net_total_return": float((1 + net_daily).prod() - 1),
            "gross_sharpe": self._sharpe(gross_daily),
            "net_sharpe": self._sharpe(net_daily),
            "max_drawdown": self._max_drawdown(net_daily),
            "cost_drag_total": float(gross_daily.sum() - net_daily.sum()),
            "n_days": int(net_daily.shape[0]),
            "n_positions": int(len(book)),
            "round_trip_cost_pct": cost_pct,
        }
        logger.info("backtest_complete", **{
            k: (round(v, 6) if isinstance(v, float) else v) for k, v in summary.items()
        })
        return {"daily_returns": net_daily, "gross_daily_returns": gross_daily,
                "summary": summary}

    @staticmethod
    def _sharpe(r: pd.Series) -> float:
        if r.std(ddof=0) == 0 or len(r) < 2:
            return 0.0
        return float(r.mean() / r.std(ddof=0) * np.sqrt(TRADING_DAYS))

    @staticmethod
    def _max_drawdown(r: pd.Series) -> float:
        if r.empty:
            return 0.0
        cum = (1 + r).cumprod()
        return float(((cum - cum.cummax()) / cum.cummax()).min())
