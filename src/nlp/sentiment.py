#!/usr/bin/env python
"""Finance-aware headline sentiment scoring (dependency-free, deterministic).

Two backends:
  * "local"  (default) -- transparent lexicon scorer, no network, no creds.
                  Honest + reproducible; used for training/eval so the signal
                  is real and auditable.
  * "kimi"   (opt-in)  -- uses src.nlp.llm_client.KimiLLMClient.parse_news
                  for richer LLM judgement. Requires a Kimi API key.

Score per headline in [-1, +1] (negative=bearish, positive=bullish).
Aggregations (mean over a day's headlines) are in [-1, +1] too.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# ── Finance-tuned lexicon ──────────────────────────────────────────────────
_POS = {
    "surge": 1.0, "surges": 1.0, "soar": 1.0, "soars": 1.0, "rally": 0.9,
    "rallies": 0.9, "gain": 0.7, "gains": 0.7, "jump": 0.8, "jumps": 0.8,
    "rise": 0.6, "rises": 0.6, "rose": 0.6, "up": 0.3, "higher": 0.6,
    "beat": 0.9, "beats": 0.9, "record": 0.8, "profit": 0.7, "profits": 0.7,
    "growth": 0.6, "grow": 0.6, "grows": 0.6, "upgrade": 0.9, "upgraded": 0.9,
    "bullish": 1.0, "outperform": 0.9, "strong": 0.5, "stronger": 0.6,
    "rebound": 0.7, "recovers": 0.6, "recover": 0.6, "optimistic": 0.7,
    "approval": 0.6, "approved": 0.6, "win": 0.7, "wins": 0.7, "boost": 0.6,
    "boosts": 0.6, "expand": 0.4, "expands": 0.4, "dividend": 0.4,
}
_NEG = {
    "fall": 0.6, "falls": 0.6, "fell": 0.6, "drop": 0.7, "drops": 0.7,
    "plunge": 1.0, "plunges": 1.0, "slump": 1.0, "slumps": 1.0, "tumble": 0.9,
    "tumbles": 0.9, "crash": 1.0, "crashes": 1.0, "loss": 0.7, "losses": 0.7,
    "decline": 0.6, "declines": 0.6, "down": 0.3, "lower": 0.6, "weak": 0.5,
    "weaker": 0.6, "miss": 0.8, "misses": 0.8, "cut": 0.5, "cuts": 0.5,
    "downgrade": 0.9, "downgraded": 0.9, "bearish": 1.0, "selloff": 0.9,
    "sell-off": 0.9, "fear": 0.6, "fears": 0.6, "warning": 0.5, "warn": 0.5,
    "lawsuit": 0.7, "probe": 0.6, "fraud": 1.0, "default": 0.9, "defaults": 0.9,
    "debt": 0.4, "slowdown": 0.7, "recession": 1.0, "layoff": 0.7, "layoffs": 0.7,
    "penalty": 0.6, "ban": 0.6, "banned": 0.6, "slashes": 0.7, "slash": 0.7,
}
_NEGATORS = {"not", "no", "never", "without", "lacks", "fails", "fail", "failed"}
_TOKEN = re.compile(r"[a-z']+")


def _local_score(text: str) -> float:
    """Lexicon scorer with simple negation handling. Returns [-1, +1]."""
    if not text:
        return 0.0
    toks = _TOKEN.findall(text.lower())
    total = 0.0
    hits = 0
    for i, tok in enumerate(toks):
        w = 0.0
        if tok in _POS:
            w = _POS[tok]
        elif tok in _NEG:
            w = -_NEG[tok]
        if w != 0.0:
            # Negation: if a negator appears in the 3 tokens before, flip.
            window = toks[max(0, i - 3):i]
            if any(n in window for n in _NEGATORS):
                w = -w
            total += w
            hits += 1
    if hits == 0:
        return 0.0
    # Squash to [-1, 1] with diminishing returns (more hits => saturates).
    raw = total / max(1.0, abs(total)) * (1.0 - 1.0 / (1.0 + abs(total)))
    return max(-1.0, min(1.0, raw))


class LocalSentimentScorer:
    """Deterministic, dependency-free headline scorer."""

    def score(self, headline: str) -> float:
        return _local_score(headline)


@dataclass
class Scored:
    text: str
    score: float


def score_headlines(
    headlines: list[str],
    provider: str = "local",
    api_key: str | None = None,
) -> list[float]:
    """Score a list of headlines. provider='local' (default) or 'kimi'."""
    if not headlines:
        return []
    if provider == "kimi":
        from src.nlp.llm_client import KimiLLMClient
        client = KimiLLMClient(api_key=api_key)
        parsed = client.parse_news(headlines)
        out = []
        for p in parsed:
            s = float(p.get("sentiment", 0.0) or 0.0)
            out.append(max(-1.0, min(1.0, s)))
        return out
    scorer = LocalSentimentScorer()
    return [scorer.score(h) for h in headlines]
