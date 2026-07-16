"""Tests that require no external services (no DB, no docker)."""
import datetime as dt

from src.common.config import load_config, _deep_merge
from src.common.exceptions import ValidationError


def test_load_config_dev():
    cfg = load_config("dev")
    assert cfg["env"] == "dev"
    assert cfg["data"]["nse"]["provider"] == "mock"


def test_load_config_overlay_merge():
    base = {"a": 1, "nested": {"x": 1, "y": 2}}
    overlay = {"nested": {"y": 99, "z": 3}}
    merged = _deep_merge(base, overlay)
    assert merged["a"] == 1
    assert merged["nested"] == {"x": 1, "y": 99, "z": 3}


def test_validation_rejects_future_date():
    future = (dt.date.today() + dt.timedelta(days=1)).isoformat()
    try:
        from src.data.validators import validate_eod_row
        validate_eod_row({
            "symbol": "X", "date": future, "open": 1, "high": 2,
            "low": 0.5, "close": 1.5, "volume": 10,
        })
        assert False, "should have raised"
    except ValidationError:
        pass


def test_validation_rejects_ohlc_violation():
    from src.data.validators import validate_eod_row
    try:
        validate_eod_row({
            "symbol": "X", "date": "2026-01-02", "open": 10, "high": 9,
            "low": 8, "close": 9.5, "volume": 10,
        })
        assert False, "should have raised"
    except ValidationError:
        pass


def test_validation_accepts_clean_row():
    from src.data.validators import validate_eod_row
    row = validate_eod_row({
        "symbol": "RELIANCE", "date": "2026-01-02", "open": 100,
        "high": 102, "low": 98, "close": 101, "volume": 1_000_000,
    })
    assert row["symbol"] == "RELIANCE"
