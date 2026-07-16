"""Symbol master: unified NSE/BSE/ISIN reconciliation (item 6 reference data).

In production this is backed by Postgres (see migrations). For the scaffold we
provide an in-memory + JSON-file backed store so collectors and tests can run
without a live DB. The interface (`upsert`, `resolve`, `all_symbols`) is the
contract the DB-backed version will implement.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from ..common.config import PROJECT_ROOT


@dataclass
class Symbol:
    nse_ticker: str
    bse_code: Optional[str] = None
    isin: Optional[str] = None
    industry: Optional[str] = None
    series: str = "EQ"

    def key(self) -> str:
        return self.nse_ticker


class SymbolMaster:
    def __init__(self, path: Path | None = None):
        self.path = path or (PROJECT_ROOT / "data" / "symbols.json")
        self._store: dict[str, Symbol] = {}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            for row in json.loads(self.path.read_text(encoding="utf-8")):
                s = Symbol(**row)
                self._store[s.key()] = s

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        rows = [asdict(s) for s in self._store.values()]
        self.path.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    # ---- contract -------------------------------------------------------
    def upsert(self, sym: Symbol) -> None:
        self._store[sym.key()] = sym
        self._save()

    def resolve(self, ticker: str) -> Optional[Symbol]:
        return self._store.get(ticker.upper())

    def all_symbols(self) -> list[Symbol]:
        return list(self._store.values())

    def reconcile(self, nse_ticker: str, *, bse_code: str | None = None,
                  isin: str | None = None, industry: str | None = None) -> Symbol:
        """Reconcile / create a symbol linking NSE<->BSE<->ISIN."""
        existing = self.resolve(nse_ticker)
        if existing:
            if bse_code: existing.bse_code = bse_code
            if isin: existing.isin = isin
            if industry: existing.industry = industry
            self._save()
            return existing
        sym = Symbol(nse_ticker.upper(), bse_code=bse_code, isin=isin,
                     industry=industry)
        self.upsert(sym)
        return sym
