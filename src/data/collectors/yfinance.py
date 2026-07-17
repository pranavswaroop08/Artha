"""Yahoo Finance EOD collector (backup source) - provider-agnostic.

Mirrors `nse.py` / `bse.py`: a `YFinanceClient` interface, a deterministic
`MockYFinanceClient` for dev/tests (no network, no `yfinance` package needed),
and a `YFinanceCollector` that fetches -> validates -> reconciles -> writes
the raw lake.

Yahoo tickers for Indian equities use the `.NS` suffix (NSE) or `.BO`
(BSE). Here the input `symbol` is treated as the NSE ticker and the mock
appends `.NS`. Real vendor clients implement `YFinanceClient.fetch_eod`.
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


class YFinanceClient(ABC):
    """Provider interface. A real yfinance-backed client implements fetch_eod."""

    @abstractmethod
    def fetch_eod(self, symbol: str, day: dt.date) -> EODBar:
        ...


class MockYFinanceClient(YFinanceClient):
    """Deterministic canned data for dev/tests. Not for production use."""

    def fetch_eod(self, symbol: str, day: dt.date) -> EODBar:
        h = abs(hash((symbol.upper(), day.isoformat()))) % 1000
        base = 200.0 + h  # offset from NSE/BSE mock ranges for clarity
        return EODBar(
            symbol=f"{symbol.upper()}.NS", date=day,
            open=round(base, 2), high=round(base * 1.02, 2),
            low=round(base * 0.98, 2), close=round(base * 1.01, 2),
            volume=500_000 + h * 100, delivery_pct=round(40.0 + (h % 50), 2),
        )


class YFinanceCollector:
    def __init__(self, client: YFinanceClient | None = None,
                 lake: RawLake | None = None,
                 symbols: SymbolMaster | None = None,
                 provider: str | None = None):
        cfg = load_config()
        self.client = client or _build_client(cfg, provider)
        self.lake = lake or RawLake()
        self.symbols = symbols or SymbolMaster()

    def collect(self, symbol: str, day: dt.date) -> EODBar:
        set_correlation_id(f"yf:{symbol}:{day}")
        bar = self.client.fetch_eod(symbol, day)
        validate_eod_row({
            "symbol": bar.symbol, "date": bar.date.isoformat(),
            "open": bar.open, "high": bar.high, "low": bar.low,
            "close": bar.close, "volume": bar.volume,
        })
        # Yahoo symbol (e.g. RELIANCE.NS) -> reconcile against NSE ticker
        nse_ticker = bar.symbol.replace(".NS", "").replace(".BO", "")
        self.symbols.reconcile(nse_ticker)
        self.lake.put(
            "yf_eod", bar.symbol, bar.date, bar.__dict__,
            event_ts=dt.datetime(day.year, day.month, day.day, 15, 30),
        )
        return bar

    def collect_range(self, symbol: str,
                      start: dt.date, end: dt.date) -> Iterator[EODBar]:
        # Prefer the client's bulk fetch_range (one HTTP call, naturally skips
        # market holidays) when the client implements it.
        bulk = getattr(self.client, "fetch_range", None)
        if bulk is not None:
            yield from bulk(symbol, start, end)
            return
        # Mock / single-day clients: iterate weekday-by-weekday.
        d = start
        one = dt.timedelta(days=1)
        while d <= end:
            if d.weekday() < 5:
                yield self.collect(symbol, d)
            d += one


def _build_client(cfg, provider: str | None = None) -> YFinanceClient:
    provider = provider or (cfg.get("data", {}).get("yfinance", {}).get("provider", "mock"))
    if provider == "mock":
        return MockYFinanceClient()
    if provider == "yfinance":
        from .yfinance_real import RealYFinanceClient
        suffix = cfg.get("data", {}).get("yfinance", {}).get("suffix", ".NS")
        return RealYFinanceClient(suffix=suffix)
    raise ValueError(f"Unknown YFinance provider: {provider!r}. Valid: 'mock', 'yfinance'.")
