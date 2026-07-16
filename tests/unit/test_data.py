import datetime as dt
import tempfile
from pathlib import Path

from src.data.raw_lake import RawLake
from src.data.symbols import SymbolMaster, Symbol
from src.data.collectors.nse import NSECollector, MockNSEClient
from src.data.validators import validate_eod_row


def test_raw_lake_idempotent_write(tmp_path):
    lake = RawLake(root=tmp_path / "lake")
    day = dt.date(2026, 7, 16)
    payload = {"close": 101.0}
    first = lake.put("nse_eod", "RELIANCE", day, payload)
    second = lake.put("nse_eod", "RELIANCE", day, payload)
    assert first is True
    assert second is False  # unchanged -> no-op
    assert lake.get("nse_eod", "RELIANCE", day) == payload


def test_raw_lake_roundtrip(tmp_path):
    lake = RawLake(root=tmp_path / "lake")
    day = dt.date(2026, 7, 16)
    lake.put("nse_eod", "INFY", day, {"close": 1500.0})
    got = lake.get("nse_eod", "INFY", day)
    assert got == {"close": 1500.0}


def test_symbol_master_reconcile(tmp_path):
    sm = SymbolMaster(path=tmp_path / "sym.json")
    s = sm.reconcile("RELIANCE", bse_code="500325", isin="INE002A01018",
                      industry="ENERGY")
    assert s.nse_ticker == "RELIANCE"
    assert s.bse_code == "500325"
    sm2 = SymbolMaster(path=tmp_path / "sym.json")
    assert sm2.resolve("RELIANCE").isin == "INE002A01018"


def test_nse_collector_mock_writes_validated(tmp_path):
    lake = RawLake(root=tmp_path / "lake")
    sm = SymbolMaster(path=tmp_path / "sym.json")
    col = NSECollector(client=MockNSEClient(), lake=lake, symbols=sm)
    bar = col.collect("RELIANCE", dt.date(2026, 7, 16))
    assert bar.close > 0
    assert lake.exists("nse_eod", "RELIANCE", dt.date(2026, 7, 16))
    assert sm.resolve("RELIANCE") is not None


def test_nse_collector_range_skips_weekends(tmp_path):
    lake = RawLake(root=tmp_path / "lake")
    col = NSECollector(client=MockNSEClient(), lake=lake,
                       symbols=SymbolMaster(path=tmp_path / "sym.json"))
    bars = list(col.collect_range("RELIANCE", dt.date(2026, 7, 13), dt.date(2026, 7, 19)))
    assert len(bars) == 5  # Mon-Fri
