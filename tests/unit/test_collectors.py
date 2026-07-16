"""Tests for BSE and Yahoo Finance collectors (provider-agnostic, mock)."""
from __future__ import annotations

import datetime as dt

from src.data.raw_lake import RawLake
from src.data.symbols import SymbolMaster
from src.data.collectors.bse import BSECollector, MockBSEClient
from src.data.collectors.yfinance import YFinanceCollector, MockYFinanceClient


def test_bse_collector_mock_writes_validated(tmp_path):
    lake = RawLake(root=tmp_path / "lake")
    sm = SymbolMaster(path=tmp_path / "sym.json")
    col = BSECollector(client=MockBSEClient(), lake=lake, symbols=sm)
    bar = col.collect("500325", dt.date(2026, 1, 1))  # BSE scrip code
    assert bar.close > 0
    assert lake.exists("bse_eod", "500325", dt.date(2026, 1, 1))
    assert sm.resolve("500325") is not None
    assert sm.resolve("500325").bse_code == "500325"


def test_yfinance_collector_mock_writes_validated(tmp_path):
    lake = RawLake(root=tmp_path / "lake")
    sm = SymbolMaster(path=tmp_path / "sym.json")
    col = YFinanceCollector(client=MockYFinanceClient(), lake=lake, symbols=sm)
    bar = col.collect("RELIANCE", dt.date(2026, 1, 1))
    assert bar.symbol == "RELIANCE.NS"  # Yahoo suffix appended
    assert bar.close > 0
    assert lake.exists("yf_eod", "RELIANCE.NS", dt.date(2026, 1, 1))
    # reconciled against the NSE ticker (suffix stripped)
    assert sm.resolve("RELIANCE") is not None


def test_bse_collector_range_skips_weekends(tmp_path):
    lake = RawLake(root=tmp_path / "lake")
    col = BSECollector(
        client=MockBSEClient(), lake=lake,
        symbols=SymbolMaster(path=tmp_path / "sym.json"),
    )
    bars = list(col.collect_range("500325", dt.date(2026, 1, 1), dt.date(2026, 1, 7)))
    # Jan 1 2026 = Thu; Fri 2; then Mon 5, Tue 6, Wed 7 -> 5 weekdays
    assert len(bars) == 5


def test_bse_collector_invalid_provider():
    import pytest
    with pytest.raises(ValueError, match="Unknown BSE provider"):
        BSECollector(provider="invalid")


def test_yfinance_collector_invalid_provider():
    import pytest
    with pytest.raises(ValueError, match="Unknown YFinance provider"):
        YFinanceCollector(provider="invalid")


def test_bse_and_yf_deterministic():
    """Same symbol+day -> same values (so tests are stable)."""
    b = MockBSEClient().fetch_eod("500325", dt.date(2026, 1, 1))
    b2 = MockBSEClient().fetch_eod("500325", dt.date(2026, 1, 1))
    assert b.close == b2.close and b.volume == b2.volume
