"""NSE EOD collector (item 9) - provider-agnostic.

NSE is anti-bot and requires a paid data vendor in production (TrueData,
EODHistoricalData, etc.). To keep the scaffold runnable + testable WITHOUT
credentials, we define:

  * `NSEClient`  -> the provider interface (what every vendor must implement).
  * `MockNSEClient` -> returns canned data; used by tests and `--dry-run`.
  * `NSECollector` -> orchestrates fetch -> validate -> write raw lake.

Swap the concrete client via config (`data.nse.provider`). No secrets are
ever committed; the real client reads its token from the environment.
"""
from __future__ import annotations

import datetime as dt
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterable, Iterator

from ...common.config import load_config, secret
from ...common.exceptions import DataError, ValidationError
from ...common.context import set_correlation_id
from ..raw_lake import RawLake
from ..symbols import SymbolMaster
from ..validators import validate_eod_row


@dataclass
class EODBar:
    symbol: str
    date: dt.date
    open: float
    high: float
    low: float
    close: float
    volume: int
    delivery_pct: float | None = None


class NSEClient(ABC):
    """Provider interface. A real vendor (TrueData, etc.) implements fetch_eod."""

    @abstractmethod
    def fetch_eod(self, symbol: str, day: dt.date) -> EODBar:
        ...


class MockNSEClient(NSEClient):
    """Deterministic canned data for dev/tests. Not for production use."""

    def fetch_eod(self, symbol: str, day: dt.date) -> EODBar:
        # deterministic pseudo-values derived from symbol+date
        h = abs(hash((symbol.upper(), day.isoformat()))) % 1000
        base = 100.0 + h
        return EODBar(
            symbol=symbol.upper(), date=day,
            open=round(base, 2), high=round(base * 1.02, 2),
            low=round(base * 0.98, 2), close=round(base * 1.01, 2),
            volume=1_000_000 + h * 100, delivery_pct=round(40.0 + (h % 50), 2),
        )


class NSECollector:
    def __init__(self, client: NSEClient | None = None,
                 lake: RawLake | None = None,
                 symbols: SymbolMaster | None = None):
        cfg = load_config()
        self.client = client or _build_client(cfg)
        self.lake = lake or RawLake()
        self.symbols = symbols or SymbolMaster()

    def collect(self, symbol: str, day: dt.date) -> EODBar:
        set_correlation_id(f"nse:{symbol}:{day}")
        bar = self.client.fetch_eod(symbol, day)
        # 1) schema/quality validation before persisting
        validate_eod_row({
            "symbol": bar.symbol, "date": bar.date.isoformat(),
            "open": bar.open, "high": bar.high, "low": bar.low,
            "close": bar.close, "volume": bar.volume,
        })
        # 2) reconcile symbol master (point-in-time, no PIT logic yet here)
        self.symbols.reconcile(bar.symbol)
        # 3) write immutable raw payload
        self.lake.put("nse_eod", bar.symbol, bar.date, bar.__dict__,
                      event_ts=dt.datetime(day.year, day.month, day.day, 15, 30))
        return bar

    def collect_range(self, symbol: str,
                      start: dt.date, end: dt.date) -> Iterator[EODBar]:
        d = start
        one = dt.timedelta(days=1)
        while d <= end:
            # skip weekends in a real run; kept simple for scaffold
            if d.weekday() < 5:
                yield self.collect(symbol, d)
            d += one


def _build_client(cfg) -> NSEClient:
    provider = (cfg.get("data", {}).get("nse", {}).get("provider", "mock"))
    if provider == "mock":
        return MockNSEClient()
    # Real providers are wired here once credentials are supplied via env.
    token = secret(f"NSE_{provider.upper()}_TOKEN")
    if not token:
        raise DataError(
            f"NSE provider '{provider}' requested but no "
            f"NSE_{provider.upper()}_TOKEN in environment. "
            f"Use provider='mock' for dev/tests."
        )
    raise NotImplementedError(
        f"Real NSE client for '{provider}' not yet implemented - "
        f"add a subclass of NSEClient and wire it in _build_client()."
    )
