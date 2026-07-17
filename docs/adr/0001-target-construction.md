# ADR-0001: Target Construction

## Status
Accepted (implemented 2026-07-17, `src/data/targets.py`)

## Context
The platform requires a rigorous definition of the prediction variable before
feature engineering or model training can begin. The target must be:
- Point-in-time safe (no lookahead bias)
- Resistant to corporate-action noise (splits/dividends)
- Aligned with the platform's output schema (multi-horizon forecast)

## Decision
The v1 target is **forward return** over horizon `h`, defined per symbol as:

```
target_fwd_ret_{h}d[T] = price_adj[T+h] / price_adj[T] - 1
```

Where:
- `price_adj` is the corporate-action-adjusted close (splits, bonuses, dividends)
- `T` is the `event_ts` (trading day)
- Alignment to row `T` is via per-symbol `groupby(symbol)[price].shift(-h)`
- The target is `NaN` for the last `h` rows of each symbol's series (future unknown)

Horizons computed: **1d, 5d, 21d**. The primary model target is **5d**; 1d/21d
are kept for research and multi-horizon calibration.

## Consequences
- Input prices MUST be adjusted via `src/data/corporate_actions.py`
  (`apply_adjustments`) before target calculation. Both splits AND dividends
  are implemented and unit-tested.
- Unadjusted prices cause false leakage/return spikes on ex-dividend dates.
- The shift is grouped by symbol — verified by a cross-symbol no-bleed test.
- Target is continuous; classification (up/down/flat) is derived downstream in
  the model layer via thresholds + (planned) conformal prediction.

## Verification
`tests/unit/test_targets.py` — 6 tests: 1d/5d math, NaN tail, missing cols,
missing price col, multi-symbol no-bleed, default horizons.
