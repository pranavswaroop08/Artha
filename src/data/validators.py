"""Data validation framework (item 10).

Lightweight, dependency-free schema contracts. Each source defines a contract;
`validate_row` raises `ValidationError` on violation. This is the scaffold
version of the Pandera/Great-Expectations layer from the design doc - the
same interface, so it can be upgraded to GE later without touching collectors.

Rejects:
  * missing required columns
  * stale timestamp (future-dated or absurdly old)
  * non-positive / zero price
  * high < low or outside [low, high] for OHLC
  * negative volume / absurd values
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from ..common.exceptions import ValidationError

# How far back we accept data before calling it stale (years).
_MAX_AGE_YEARS = 10
_REQUIRED_EOD = ("symbol", "date", "open", "high", "low", "close", "volume")


def _as_date(v: Any) -> date:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, str):
        return date.fromisoformat(v[:10])
    raise ValidationError(f"Unparseable date: {v!r}")


def validate_eod_row(row: dict[str, Any]) -> dict[str, Any]:
    """Validate one EOD row; returns the normalized row or raises ValidationError."""
    missing = [c for c in _REQUIRED_EOD if c not in row or row[c] is None]
    if missing:
        raise ValidationError(f"EOD row missing fields {missing}: {row!r}")

    try:
        d = _as_date(row["date"])
    except Exception as e:
        raise ValidationError(f"Bad date in EOD row: {e}") from e

    today = date.today()
    if d > today:
        raise ValidationError(f"EOD date is in the future: {d}")
    if (today.year - d.year) > _MAX_AGE_YEARS:
        raise ValidationError(f"EOD date too old (> {_MAX_AGE_YEARS}y): {d}")

    o, h, l, c, v = (row["open"], row["high"], row["low"],
                         row["close"], row["volume"])
    for name, val in (("open", o), ("high", h), ("low", l), ("close", c)):
        if not isinstance(val, (int, float)) or val <= 0:
            raise ValidationError(f"Non-positive price {name}={val} for {row['symbol']}")
    if not isinstance(v, int) or v < 0:
        raise ValidationError(f"Negative volume {v} for {row['symbol']}")
    if not (l <= o <= h and l <= c <= h):
        raise ValidationError(
            f"OHLC violation for {row['symbol']} {d}: "
            f"low={l} open={o} close={c} high={h}"
        )
    return row


def _as_datetime(v: Any) -> datetime:
    """Coerce date/datetime/str to datetime for PIT checks."""
    if isinstance(v, datetime):
        return v
    if isinstance(v, date):
        return datetime(v.year, v.month, v.day)
    if isinstance(v, str):
        return datetime.fromisoformat(v[:19]) if "T" in v[:19] else datetime.fromisoformat(v[:10])
    raise ValidationError(f"Unparseable timestamp: {v!r}")


def validate_pit_row(row: dict[str, Any]) -> dict[str, Any]:
    """Validate a point-in-time row for delayed-reporting sources.

    Enforces the invariant ``as_of_ts >= event_ts``: data cannot be knowable
    before the event that produced it. Raises ValidationError otherwise.

    Also rejects an ``as_of_ts`` in the future (data from tomorrow is not
    knowable today).
    """
    for col in ("event_ts", "as_of_ts"):
        if col not in row or row[col] is None:
            raise ValidationError(f"PIT row missing '{col}': {row!r}")
    event_ts = _as_datetime(row["event_ts"])
    as_of_ts = _as_datetime(row["as_of_ts"])
    if as_of_ts < event_ts:
        raise ValidationError(
            f"PIT violation: as_of_ts {as_of_ts} < event_ts {event_ts} "
            f"for {row.get('symbol', '?')}"
        )
    if as_of_ts > datetime.now():
        raise ValidationError(f"PIT row as_of_ts is in the future: {as_of_ts}")
    return row


# Registry of contracts by source name - extend as collectors land.
CONTRACTS = {
    "nse_eod": validate_eod_row,
    "pit_delayed": validate_pit_row,
}



def validate(source: str, row: dict[str, Any]) -> dict[str, Any]:
    fn = CONTRACTS.get(source)
    if fn is None:
        raise ValidationError(f"No contract registered for source '{source}'")
    return fn(row)
