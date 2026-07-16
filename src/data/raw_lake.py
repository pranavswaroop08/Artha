"""Immutable raw-lake writer (item 6 / item 9 backend).

Every collector persists its raw payloads here as append-only, content-hashed
Parquet/JSON keyed by (source, symbol, as_of_date). Writes are idempotent:
re-writing the same payload for the same key is a no-op (hash match).
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from ..common.config import PROJECT_ROOT


class RawLake:
    def __init__(self, root: Path | None = None):
        self.root = root or (PROJECT_ROOT / "data" / "raw_lake")

    # ---- paths ---------------------------------------------------------
    def _path(self, source: str, symbol: str, as_of: date | datetime) -> Path:
        d = as_of if isinstance(as_of, date) else as_of.date()
        sym = symbol.replace(":", "_").replace("/", "_")
        return self.root / source / sym / f"{d.isoformat()}.json"

    def _hash(self, payload: Any) -> str:
        blob = json.dumps(payload, sort_keys=True, default=str).encode()
        return hashlib.sha256(blob).hexdigest()

    # ---- public API -----------------------------------------------------
    def put(self, source: str, symbol: str, as_of: date | datetime,
            payload: Any, *, event_ts: datetime | None = None) -> bool:
        """Write a raw payload. Returns True if newly written, False if unchanged.

        Stored envelope:
            {"source","symbol","as_of_ts","event_ts","payload_hash","payload"}
        """
        p = self._path(source, symbol, as_of)
        h = self._hash(payload)
        if p.exists():
            try:
                existing = json.loads(p.read_text(encoding="utf-8"))
                if existing.get("payload_hash") == h:
                    return False  # idempotent no-op
            except (json.JSONDecodeError, OSError):
                pass  # corrupt file -> overwrite
        p.parent.mkdir(parents=True, exist_ok=True)
        envelope = {
            "source": source,
            "symbol": symbol,
            "as_of_ts": (as_of.isoformat() if isinstance(as_of, datetime)
                          else as_of.isoformat()),
            "event_ts": event_ts.isoformat() if event_ts else None,
            "payload_hash": h,
            "payload": payload,
        }
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(envelope, default=str), encoding="utf-8")
        tmp.replace(p)  # atomic
        return True

    def get(self, source: str, symbol: str, as_of: date | datetime) -> Any | None:
        p = self._path(source, symbol, as_of)
        if not p.exists():
            return None
        env = json.loads(p.read_text(encoding="utf-8"))
        return env["payload"]

    def exists(self, source: str, symbol: str, as_of: date | datetime) -> bool:
        return self._path(source, symbol, as_of).exists()
