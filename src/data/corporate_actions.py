"""Corporate Actions collection and price adjustment (Rule B enabler).

Accurate forward returns (targets.py) REQUIRE corporate-action-adjusted
prices. A 2:1 split mechanically halves the raw close; without adjustment the
target module would "see" a -50% crash on the ex-date and learn a false
signal. This module (a) collects action events with PIT timestamps and
(b) backward-adjusts OHLCV so the price series is continuous.

PIT note: backward adjustment inherently uses the *known* ex-date to rewrite
history -- this is standard and correct for a continuous price series used in
backtests/features, because the adjustment is a fixed function of public ex-dates,
not of future *returns*. The collector still records ``as_of_ts`` (announcement)
and ``event_ts`` (ex-date) so the feature store knows when each action became
public. Dividend adjustment uses the ex-date close as the reference.
"""
from __future__ import annotations

import datetime as dt
from abc import ABC, abstractmethod
from typing import Protocol

import pandas as pd

from ..common.config import load_config
from ..common.exceptions import ValidationError
from ..common.context import set_correlation_id
from .raw_lake import RawLake


class CorporateActionsClient(Protocol):
    def get_actions(
        self, symbol: str, start_date: dt.date, end_date: dt.date
    ) -> pd.DataFrame:
        ...


class MockCorporateActionsClient:
    """Deterministic mock: a 2:1 split on 2026-01-03 for any symbol."""

    def get_actions(
        self, symbol: str, start_date: dt.date, end_date: dt.date
    ) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "symbol": symbol,
                    "event_ts": pd.Timestamp("2026-01-03"),  # ex-date
                    "as_of_ts": pd.Timestamp("2026-01-02"),  # announced day before
                    "action_type": "SPLIT",
                    "value": 2.0,  # 2 new shares for 1 old
                }
            ]
        )


class CorporateActionsCollector:
    def __init__(
        self,
        client: CorporateActionsClient | None = None,
        lake: RawLake | None = None,
        provider: str | None = None,
    ):
        cfg = load_config()
        self.client = client or _build_client(cfg, provider)
        self.lake = lake or RawLake()

    def collect(
        self, symbol: str, start_date: dt.date, end_date: dt.date
    ) -> pd.DataFrame:
        set_correlation_id(f"corpacts:{symbol}:{start_date}:{end_date}")
        df = self.client.get_actions(symbol, start_date, end_date)
        required = ["symbol", "event_ts", "as_of_ts", "action_type", "value"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValidationError(
                f"Corporate actions missing columns {missing}: {list(df.columns)}"
            )
        return df

    def collect_range(
        self, symbol: str, start_date: dt.date, end_date: dt.date
    ) -> pd.DataFrame:
        return self.collect(symbol, start_date, end_date)


def _build_client(cfg, provider: str | None = None) -> CorporateActionsClient:
    provider = provider or (
        cfg.get("data", {}).get("corporate_actions", {}).get("provider", "mock")
    )
    if provider == "mock":
        return MockCorporateActionsClient()
    # Real providers (NSE/BSE corporate-actions feeds) wired here.
    raise ValueError(f"Unknown corporate actions provider: {provider}")


def apply_adjustments(
    prices_df: pd.DataFrame, actions_df: pd.DataFrame
) -> pd.DataFrame:
    """Backward-adjust OHLCV for splits and dividends.

    Args:
        prices_df: Must contain ``event_ts``, ``open``, ``high``, ``low``,
            ``close``, ``volume``.
        actions_df: Must contain ``event_ts`` (ex-date), ``action_type``
            (SPLIT | DIVIDEND), ``value`` (split ratio, or dividend per share).

    Returns:
        Copy with ``*_adj`` columns. Pre-ex-date rows are adjusted; on/after
        the ex-date rows are unchanged.
    """
    required = ["event_ts", "open", "high", "low", "close", "volume"]
    missing = [c for c in required if c not in prices_df.columns]
    if missing:
        raise ValidationError(f"prices_df missing columns {missing}")

    df = prices_df.copy()
    df["event_ts"] = pd.to_datetime(df["event_ts"])
    df = df.sort_values("event_ts").reset_index(drop=True)

    price_factor = pd.Series(1.0, index=df.index)
    vol_factor = pd.Series(1.0, index=df.index)

    if actions_df is not None and not actions_df.empty:
        actions = actions_df.copy()
        actions["event_ts"] = pd.to_datetime(actions["event_ts"])
        actions = actions.sort_values("event_ts")
        for _, act in actions.iterrows():
            ex = act["event_ts"]
            mask = df["event_ts"] < ex
            if act["action_type"] == "SPLIT":
                ratio = float(act["value"])
                if ratio <= 0:
                    continue
                # Pre-split prices divided by ratio; pre-split volumes scaled up.
                price_factor[mask] /= ratio
                vol_factor[mask] *= ratio
            elif act["action_type"] == "DIVIDEND":
                div = float(act["value"])
                ref_row = df.loc[df["event_ts"] == ex, "close"]
                if ref_row.empty or ref_row.iloc[0] == 0:
                    continue
                ref = float(ref_row.iloc[0])
                # Pre-ex close reduced by the dividend proportionally.
                price_factor[mask] *= 1.0 - div / ref

    df["open_adj"] = df["open"] * price_factor
    df["high_adj"] = df["high"] * price_factor
    df["low_adj"] = df["low"] * price_factor
    df["close_adj"] = df["close"] * price_factor
    df["volume_adj"] = df["volume"] * vol_factor
    return df
