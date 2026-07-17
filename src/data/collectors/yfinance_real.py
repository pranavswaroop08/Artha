"""Real Yahoo Finance EOD client.

Implements the ``YFinanceClient`` interface from ``yfinance.py`` using the
``yfinance`` package (free, no API key). NSE tickers get the ``.NS`` suffix;
BSE tickers get ``.BO``.

Usage (wired automatically when ``data.yfinance.provider: yfinance`` in config,
or pass ``provider="yfinance"`` to ``YFinanceCollector``):

    from src.data.collectors.yfinance import YFinanceCollector
    from datetime import date

    col = YFinanceCollector(provider="yfinance")
    bar = col.collect("RELIANCE", date.today())

    # Or a date range:
    bars = list(col.collect_range("TCS", date(2024, 1, 1), date(2024, 6, 30)))

PIT note: ``event_ts`` is set to 15:30 IST on the bar date (NSE/BSE close).
``as_of_ts`` is the same — EOD data is public at close time (no delayed
disclosure for price data, unlike fundamentals).

Anti-patterns to avoid
----------------------
* Do NOT use ``yf.download(auto_adjust=False)`` — always use ``auto_adjust=True``
  (default) so splits/dividends are baked in, preventing false return spikes.
* Do NOT pass tomorrow's date — yfinance silently returns an empty frame.
"""
from __future__ import annotations

import datetime as dt
from typing import Iterator

from .nse import EODBar
from .yfinance import YFinanceClient, YFinanceCollector
from ...common.context import get_logger
from ...common.exceptions import DataError

logger = get_logger(__name__)


class RealYFinanceClient(YFinanceClient):
    """Thin wrapper around the ``yfinance`` package.

    Fetches one trading day at a time for simplicity (batch via
    ``collect_range`` uses a single multi-day download for efficiency).
    """

    def __init__(self, suffix: str = ".NS"):
        """Args:
            suffix: Yahoo ticker suffix — ``.NS`` for NSE (default), ``.BO`` for BSE.
        """
        try:
            import yfinance  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "yfinance is not installed. Run: pip install yfinance"
            ) from exc
        self.suffix = suffix

    def fetch_eod(self, symbol: str, day: dt.date) -> EODBar:
        """Fetch a single EOD bar.

        Downloads a 2-day window (day → day+1) so yfinance returns the
        target day's row even when the next trading day hasn't occurred yet.
        """
        import yfinance as yf

        ticker = f"{symbol.upper()}{self.suffix}"
        end = day + dt.timedelta(days=1)

        df = yf.download(
            ticker,
            start=day.isoformat(),
            end=end.isoformat(),
            auto_adjust=True,    # adjusts for splits + dividends (Rule B: clean returns)
            progress=False,
            actions=False,
        )

        if df.empty:
            raise DataError(
                f"yfinance returned no data for {ticker} on {day}. "
                "Check the ticker/suffix and that the market was open."
            )

        # yfinance returns a DatetimeIndex; grab the row closest to target date.
        row = df.iloc[0]
        volume = int(row["Volume"].iloc[0]) if "Volume" in row.index else 0

        bar = EODBar(
            symbol=symbol.upper(),
            date=day,
            open=float(row["Open"].iloc[0]),
            high=float(row["High"].iloc[0]),
            low=float(row["Low"].iloc[0]),
            close=float(row["Close"].iloc[0]),
            volume=volume,
            delivery_pct=None,  # not available from yfinance
        )
        logger.info("yfinance_eod_fetched", symbol=ticker, date=day.isoformat(),
                    close=bar.close, volume=bar.volume)
        return bar

    def fetch_range(
        self, symbol: str, start: dt.date, end: dt.date
    ) -> Iterator[EODBar]:
        """Efficient bulk download — one yfinance call for the whole range.

        Preferred over calling ``fetch_eod`` in a loop because yfinance
        batches the HTTP request.
        """
        import yfinance as yf
        import pandas as pd

        ticker = f"{symbol.upper()}{self.suffix}"
        # end is exclusive in yfinance
        yf_end = (end + dt.timedelta(days=1)).isoformat()

        df = yf.download(
            ticker,
            start=start.isoformat(),
            end=yf_end,
            auto_adjust=True,
            progress=False,
            actions=False,
        )

        if df.empty:
            logger.warning("yfinance_range_empty", symbol=ticker,
                           start=start.isoformat(), end=end.isoformat())
            return

        # Flatten MultiIndex columns if present (happens with single ticker too
        # in newer yfinance versions).
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        for ts, row in df.iterrows():
            bar_date = ts.date() if hasattr(ts, "date") else ts
            volume = int(row.get("Volume", 0).iloc[0])
            try:
                bar = EODBar(
                    symbol=symbol.upper(),
                    date=bar_date,
                    open=float(row["Open"].iloc[0]),
                    high=float(row["High"].iloc[0]),
                    low=float(row["Low"].iloc[0]),
                    close=float(row["Close"].iloc[0]),
                    volume=volume,
                    delivery_pct=None,
                )
            except (KeyError, TypeError, ValueError) as exc:
                logger.warning("yfinance_row_skipped", symbol=ticker,
                               date=str(bar_date), error=str(exc))
                continue
            yield bar
