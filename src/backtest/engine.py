"""Vectorized long-only backtest engine with Indian-cost overlay.

Alignment (PIT-safe, single shift): a prediction made at ``event_ts = T`` is
traded at the next bar and earns the return ``close[T+1]/close[T] - 1``. We
compute the forward 1-day return per symbol and pair it with the CURRENT-row
prediction; the last bar of each symbol has no forward return and is dropped.
There is NO second shift of the prediction -- doing both (lag pred AND lead
return) opens a 2-day gap and is a bug.

Costs: charged only on ACTUAL TURNOVER -- the fraction of the book that changes
on each rebalance day. A symbol held continuously incurs no cost; it pays only
when it enters the top-N book (round-trip amortised to entry day). This is the
realistic model for a weekly-rebalanced strategy:
  - Round-trip cost per name = buy_bps + sell_bps (delivery schedule).
  - Per-day cost = round_trip_cost x (n_entries / top_n).
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
        hold_days: int = 1,
        long_short: bool = False,
    ):
        """Args:
            top_n: number of names on each side (long leg; short leg mirrors it
                   when long_short=True).
            hold_days: Rebalance every N trading days (default 1 = daily).
                       Set to the forecast horizon (e.g. 5) to match the
                       prediction frequency and minimise turnover.
            long_short: if True, long top-N AND short bottom-N (dollar-neutral,
                   beta ~ 0). Isolates the model's alpha from market direction.
        """
        if top_n < 1:
            raise ValueError("top_n must be >= 1")
        if hold_days < 1:
            raise ValueError("hold_days must be >= 1")
        self.top_n = top_n
        self.cost_model = cost_model or IndianCostModel()
        self.notional_per_leg_inr = notional_per_leg_inr
        self.hold_days = hold_days
        self.long_short = long_short

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

        # ── Rebalance schedule: only trade every hold_days bars ──────────
        sorted_dates = sorted(df["event_ts"].unique())
        rebalance_set = set(sorted_dates[i] for i in range(0, len(sorted_dates), self.hold_days))

        # Daily top-N long book using the LAST rebalance day's predictions.
        # On non-rebalance days, carry forward the previous book.
        df["rank"] = np.nan
        current_pred = None
        for date in sorted_dates:
            day_mask = df["event_ts"] == date
            if date in rebalance_set:
                current_pred = df.loc[day_mask, prediction_col].copy()
                current_pred.index = df.loc[day_mask, "symbol"].values
            if current_pred is not None:
                # Assign rank from latest rebalance snapshot to today's rows
                day_syms = df.loc[day_mask, "symbol"]
                avail = current_pred.reindex(day_syms.values)
                avail.index = df.index[day_mask]
                ranked = avail.rank(ascending=False, method="first", na_option="bottom")
                df.loc[day_mask, "rank"] = ranked.values

        book = df[df["rank"] <= self.top_n].copy()
        book["weight"] = 1.0 / self.top_n
        book["gross_ret"] = book["weight"] * book["fwd_ret_1d"]

        # Market-neutral extension: also short the BOTTOM-N names PER REBALANCE
        # DAY, so the book is dollar-neutral (beta ~ 0). This isolates the
        # model's alpha from market direction -- a long-only book in a bull
        # market looks profitable even with zero IC (proven via random-pred test).
        if self.long_short:
            # Short the BOTTOM-N names per rebalance day (rank is 1=best, so
            # bottom-N = rank > (max_rank - top_n)). Dollar-neutral vs the
            # long leg. This isolates alpha from market direction.
            n_sym_day = df.groupby("event_ts")["rank"].transform("max")
            short_mask = df["rank"] > (n_sym_day - self.top_n)
            short_book = df[short_mask].copy()
            short_book["weight"] = -1.0 / self.top_n
            short_book["gross_ret"] = short_book["weight"] * short_book["fwd_ret_1d"]
            book = pd.concat([book, short_book], ignore_index=True)

        # ── Turnover-based cost (charge only on rebalance days) ──────────
        cost_pct = self._round_trip_cost_pct()
        daily_cost: dict = {}
        prev_held: set = set()
        for date in sorted(book["event_ts"].unique()):
            today_held = set(book.loc[book["event_ts"] == date, "symbol"])
            if date in rebalance_set:
                n_entries = len(today_held - prev_held)
                daily_cost[date] = (n_entries / self.top_n) * cost_pct
                prev_held = today_held
            else:
                daily_cost[date] = 0.0

        # Distribute each day's total cost equally across held positions
        book["cost_drag"] = book["event_ts"].map(daily_cost).fillna(0.0) / self.top_n
        book["net_ret"] = book["gross_ret"] - book["cost_drag"]

        gross_daily = book.groupby("event_ts")["gross_ret"].sum()
        net_daily   = book.groupby("event_ts")["net_ret"].sum()

        # Average daily turnover fraction (0=no turnover, 1=full book replaced)
        avg_turnover = float(
            pd.Series(list(daily_cost.values())).mean() / cost_pct
        ) if cost_pct > 0 else 0.0

        summary = {
            "gross_total_return":      float((1 + gross_daily).prod() - 1),
            "net_total_return":        float((1 + net_daily).prod() - 1),
            "gross_sharpe":            self._sharpe(gross_daily),
            "net_sharpe":              self._sharpe(net_daily),
            "max_drawdown":            self._max_drawdown(net_daily),
            "cost_drag_total":         float(gross_daily.sum() - net_daily.sum()),
            "n_days":                  int(net_daily.shape[0]),
            "n_positions":             int(len(book)),
            "round_trip_cost_pct":     cost_pct,
            "avg_daily_turnover_pct":  avg_turnover,
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
