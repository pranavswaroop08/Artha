"""Backtest significance + performance stats.

Two tools that stop a backtest from lying to you:

1. Deflated Sharpe Ratio (Bailey & Pópelař, 2014): adjusts the observed Sharpe
   for the number of trials (strategies / parameter combinations tested) and
   for autocorrelation (negatively-autocorrelated returns inflate the naive
   Sharpe). A strategy that survives deflation is not a lucky draw.

2. Alpha vs a market factor: regress portfolio daily returns on the cross-
   sectional market return (equal-weight of all names). The intercept is the
   model's true alpha (beta-neutral edge); the beta tells you how much of the
   PnL was just market direction.
"""
from __future__ import annotations

from typing import Dict, Optional

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def deflated_sharpe(
    returns: pd.Series,
    n_trials: int = 1,
    sharpe_anchor: float = 0.0,
    skew: Optional[float] = None,
    kurtosis: Optional[float] = None,
) -> Dict[str, float]:
    """Bailey-Pópelař deflated Sharpe ratio (prob. it beats the anchor).

    Returns the *p-value* (lower = more significant) and the deflated Sharpe
    estimate. Uses the closed-form normal approximation; for the skew/kurtosis
    correction we pass sample moments when available.
    """
    r = returns.dropna()
    n = len(r)
    if n < 10:
        return {"deflated_sharpe": float("nan"), "p_value": float("nan"), "naive_sharpe": 0.0}

    sr = float(r.mean() / r.std(ddof=0) * np.sqrt(TRADING_DAYS))
    # Sample skew/kurtosis if not supplied.
    g1 = float(r.skew()) if skew is None else skew
    g2 = float(r.kurt()) if kurtosis is None else kurtosis
    # Autocorrelation correction (lag-1) — negatively autocorrelated returns
    # (common for daily rebalanced) overstate the IID Sharpe.
    ac1 = float(r.autocorr(1)) if n > 2 else 0.0
    var_adjust = (1.0 + 2.0 * ac1) / (1.0 - 2.0 * ac1) if abs(ac1) < 0.49 else 1.0

    # Standard error of the Sharpe (assuming normality, Lo 2002 form).
    se_sr = np.sqrt((1.0 - ac1) / max(n - 1, 1)) * np.sqrt(var_adjust)
    # SPA-style: SR relative to anchor, scaled by sqrt(n_trials) (multiple-testing)
    z = (sr - sharpe_anchor) / (se_sr * np.sqrt(n_trials))
    # Normal CDF of z -> p-value that SR <= anchor (i.e. no edge).
    from math import erf, sqrt

    def norm_cdf(x: float) -> float:
        return 0.5 * (1.0 + erf(x / sqrt(2.0)))

    p_value = 1.0 - norm_cdf(z)
    return {
        "naive_sharpe": sr,
        "deflated_sharpe": sr / np.sqrt(n_trials),
        "p_value": float(p_value),
        "ac1": ac1,
    }


def market_alpha(
    portfolio_returns: pd.Series,
    market_returns: pd.Series,
) -> Dict[str, float]:
    """Regress portfolio daily returns on the market factor.

    Returns alpha (annualised, the real edge), beta (market exposure), and
    the R^2 (how much of the PnL is explained by beta). Aligned on dates.
    """
    df = pd.concat(
        [portfolio_returns.rename("port"), market_returns.rename("mkt")], axis=1
    ).dropna()
    if len(df) < 10:
        return {"alpha_ann": float("nan"), "beta": float("nan"), "r2": float("nan")}
    y = df["port"].values
    x = df["mkt"].values
    xc = x - x.mean()
    beta = float((xc * (y - y.mean())).sum() / (xc * xc).sum())
    # Uncentered intercept = daily alpha (in original units).
    alpha_daily = float(y.mean() - beta * x.mean())
    alpha_ann = alpha_daily * TRADING_DAYS
    yhat = beta * xc + y.mean()
    ss_res = float(((y - yhat) ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return {"alpha_ann": alpha_ann, "beta": beta, "r2": float(r2)}
