"""BSE EOD collector - provider-agnostic.

Mirrors `nse.py`: a `BSEClient` interface, a deterministic `MockBSEClient`
for dev/tests (no network, no credentials), and a `BSECollector` that
orchestrates fetch -> validate -> symbol reconcile -> raw lake write.

BSE identifies securities by a 6-digit scrip code (e.g. 500325 = Reliance).
Yahoo uses the `.BO` suffix for BSE; here we treat the input `symbol` as the
BSE scrip code. Real vendor clients (paid BSE/TrueData feeds) implement
`BSEClient.fetch_eod`.
"""
from __future__ import annotations

import datetime as dt
from abc import ABC, abstractmethod
from typing import Iterator

from ...common.config import load_config
from ...common.exceptions import ValidationError
from ...common.context import set_correlation_id
from ..raw_lake import RawLake
from ..symbols import SymbolMaster
from ..validators import validate_eod_row
from .nse import EODBar


class BSEClient(ABC):
    """Provider interface. A real BSE vendor implements fetch_eod."""

    @abstractmethod
    def fetch_eod(self, symbol: str, day: dt.date) -> EODBar:
        ...


class MockBSEClient(BSEClient):
    """Deterministic canned data for dev/tests. Not for production use."""

    def fetch_eod(self, symbol: str, day: dt.date) -> EODBar:
        h = abs(hash((symbol.upper(), day.isoformat()))) % 1000
        base = 100.0 + h
        return EODBar(
            symbol=symbol.upper(), date=day,
            open=round(base, 2), high=round(base * 1.02, 2),
            low=round(base * 0.98, 2), close=round(base * 1.01, 2),
            volume=1_000_000 + h * 100, delivery_pct=round(40.0 + (h % 50), 2),
        )


class BSECollector:
    def __init__(self, client: BSEClient | None = None,
                 lake: RawLake | None = None,
                 symbols: SymbolMaster | None = None,
                 provider: str | None = None):
        cfg = load_config()
        self.client = client or _build_client(cfg, provider)
        self.lake = lake or RawLake()
        self.symbols = symbols or SymbolMaster()

    def collect(self, symbol: str, day: dt.date) -> EODBar:
        set_correlation_id(f"bse:{symbol}:{day}")
        bar = self.client.fetch_eod(symbol, day)
        # 1) schema/quality validation before persisting
        validate_eod_row({
            "symbol": bar.symbol, "date": bar.date.isoformat(),
            "open": bar.open, "high": bar.high, "low": bar.low,
            "close": bar.close, "volume": bar.volume,
        })
        # 2) reconcile symbol master (BSE scrip code)
        self.symbols.reconcile(bar.symbol, bse_code=bar.symbol)
        # 3) write immutable raw payload (PIT: event_ts = market close IST)
        self.lake.put(
            "bse_eod", bar.symbol, bar.date, bar.__dict__,
            event_ts=dt.datetime(day.year, day.month, day.day, 15, 30),
        )
        return bar

    def collect_range(self, symbol: str,
                      start: dt.date, end: dt.date) -> "Iterator[EODBar]":
        d = start
        one = dt.timedelta(days=1)
        while d <= end:
            if d.weekday() < 5:  # skip weekends
                yield self.collect(symbol, d)
            d += one


def _build_client(cfg, provider: str | None = None) -> BSEClient:
    provider = provider or (cfg.get("data", {}).get("bse", {}).get("provider", "mock"))
    if provider != "mock":
        # Only the mock client is implemented today. Real BSE vendor clients
        # (TrueData, etc.) get wired here, reading BSE_<PROVIDER>_TOKEN.
        raise ValueError(f"Unknown BSE provider: {provider}")
    return MockBSEClient()
