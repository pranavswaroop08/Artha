"""Tests for backtest significance stats (deflated Sharpe, market alpha)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.backtest.stats import deflated_sharpe, market_alpha


def test_deflated_sharpe_high_for_real_edge():
    rng = np.random.default_rng(0)
    # Deterministic small edge: shift the sample mean up so Sharpe is clearly >0.5.
    r = pd.Series(rng.normal(0.0, 0.01, 2000) + 0.0006)
    ds = deflated_sharpe(r, n_trials=1)
    assert ds["naive_sharpe"] > 0.5
    assert 0.0 <= ds["p_value"] <= 1.0
    # Deflated SR scales down with trials.
    ds20 = deflated_sharpe(r, n_trials=20)
    assert ds20["deflated_sharpe"] == pytest.approx(ds["naive_sharpe"] / np.sqrt(20), rel=1e-6)


def test_deflated_sharpe_random_noise_not_significant():
    rng = np.random.default_rng(1)
    r = pd.Series(rng.normal(0.0, 0.01, 500))  # pure noise
    ds = deflated_sharpe(r, n_trials=20)
    # Function returns sane, bounded values for noise.
    assert 0.0 <= ds["p_value"] <= 1.0
    assert np.isfinite(ds["naive_sharpe"])
    assert np.isfinite(ds["deflated_sharpe"])


def test_market_alpha_recovers_zero_for_market_only():
    # Portfolio == market exactly -> alpha 0, beta 1, R^2 1.
    rng = np.random.default_rng(2)
    mkt = pd.Series(rng.normal(0.0004, 0.01, 600))
    port = mkt + rng.normal(0.0, 1e-9, 600)
    ma = market_alpha(port, mkt)
    assert ma["alpha_ann"] == pytest.approx(0.0, abs=1e-6)
    assert ma["beta"] == pytest.approx(1.0, abs=1e-6)
    assert ma["r2"] == pytest.approx(1.0, abs=1e-6)


def test_market_alpha_detects_real_alpha():
    rng = np.random.default_rng(3)
    mkt = pd.Series(rng.normal(0.0004, 0.01, 800))
    # Portfolio = market + constant daily alpha + noise.
    alpha_daily = 0.0002
    port = mkt + alpha_daily + rng.normal(0.0, 0.005, 800)
    ma = market_alpha(port, mkt)
    # Annualised alpha ~ 0.0002*252 = 0.0504; noise +/- a few percent.
    assert ma["alpha_ann"] == pytest.approx(0.0504, abs=0.06)
    assert 0.0 < ma["r2"] < 1.0
