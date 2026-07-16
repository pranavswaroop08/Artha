"""Tests for Point-in-Time (PIT) discipline and lineage tracking."""
from __future__ import annotations

import pandas as pd
import pytest

from src.data.pit import (
    get_pit_dataframe,
    assert_no_future_leakage,
    FutureLeakError,
    LeakageError,
)
from src.data.lineage import LineageTracker, compute_dataframe_hash


@pytest.fixture
def sample_pit_data() -> pd.DataFrame:
    """Data with delayed reporting (as_of_ts lags event_ts)."""
    return pd.DataFrame(
        {
            "symbol": ["RELIANCE", "RELIANCE", "RELIANCE"],
            "event_ts": pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03"]),
            "as_of_ts": pd.to_datetime(
                ["2026-01-01", "2026-01-03", "2026-01-04"]
            ),  # Jan 2 event reported Jan 3
            "close": [100, 105, 102],
        }
    )


def test_pit_filter_blocks_future_data(sample_pit_data):
    current_ts = pd.Timestamp("2026-01-02")
    pit_df = get_pit_dataframe(sample_pit_data, current_ts)

    # Only the Jan-1 row is knowable by Jan 2 (Jan-2 event reported Jan 3).
    assert len(pit_df) == 1
    assert pit_df.iloc[0]["event_ts"] == pd.Timestamp("2026-01-01")


def test_pit_filter_allows_past_and_current(sample_pit_data):
    current_ts = pd.Timestamp("2026-01-03")
    pit_df = get_pit_dataframe(sample_pit_data, current_ts)

    assert len(pit_df) == 2
    assert pit_df["event_ts"].max() <= pd.Timestamp("2026-01-02")


def test_pit_missing_column_raises():
    bad_df = pd.DataFrame({"event_ts": [pd.Timestamp("2026-01-01")]})
    with pytest.raises(ValueError, match="must contain 'as_of_ts'"):
        get_pit_dataframe(bad_df, pd.Timestamp("2026-01-02"))


def test_assert_no_future_leakage_passes(sample_pit_data):
    pit_df = get_pit_dataframe(sample_pit_data, pd.Timestamp("2026-01-03"))
    assert_no_future_leakage(pit_df, pd.Timestamp("2026-01-03"))  # no raise


def test_assert_no_future_leakage_fails(sample_pit_data):
    with pytest.raises((FutureLeakError, LeakageError), match="Future leakage"):
        assert_no_future_leakage(sample_pit_data, pd.Timestamp("2026-01-02"))


def test_lineage_tracker_computes_consistent_hash(sample_pit_data):
    tracker = LineageTracker()
    h1 = tracker.log_input("raw_bars", sample_pit_data)
    h2 = compute_dataframe_hash(sample_pit_data)
    assert h1 == h2
    # determinism: same data -> same hash
    assert compute_dataframe_hash(sample_pit_data) == h2


def test_lineage_tracker_logs_transformation(sample_pit_data):
    tracker = LineageTracker()
    tracker.log_input("raw_bars", sample_pit_data)

    filtered_df = get_pit_dataframe(sample_pit_data, pd.Timestamp("2026-01-03"))
    tracker.log_output("pit_bars", filtered_df, step_name="pit_filter")

    record = tracker.get_lineage_record()
    assert len(record["lineage_history"]) == 2
    assert record["lineage_history"][0]["step"] == "input"
    assert record["lineage_history"][1]["step"] == "output"
    assert record["lineage_history"][1]["process"] == "pit_filter"
    assert record["final_hash"] == record["lineage_history"][1]["hash"]


def test_validate_pit_row_rejects_as_of_before_event():
    from src.data.validators import validate_pit_row

    row = {
        "symbol": "RELIANCE",
        "event_ts": "2026-01-03",
        "as_of_ts": "2026-01-02",  # knowable BEFORE the event -> violation
    }
    with pytest.raises(Exception, match="PIT violation"):
        validate_pit_row(row)


def test_validate_pit_row_accepts_valid_delayed_row():
    from src.data.validators import validate_pit_row

    row = {
        "symbol": "RELIANCE",
        "event_ts": "2026-01-02",
        "as_of_ts": "2026-01-03",  # reported next day: valid
    }
    assert validate_pit_row(row)["symbol"] == "RELIANCE"
