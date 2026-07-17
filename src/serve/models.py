"""Pydantic models for the serving API — the platform's output contract.

Probabilities are validated to be in [0,1] and to sum to ~1.0, so an invalid
prediction can never leave the API (fail-closed contract).
"""
from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field, field_validator, model_validator


class PredictionRequest(BaseModel):
    symbol: str = Field(..., min_length=1)
    as_of_ts: str  # ISO-8601 string


class ContributingFactor(BaseModel):
    feature: str
    impact: float
    direction: str

    @field_validator("direction")
    @classmethod
    def _dir(cls, v: str) -> str:
        if v not in {"up", "down", "neutral"}:
            raise ValueError("direction must be 'up', 'down', or 'neutral'")
        return v


class PredictionResponse(BaseModel):
    symbol: str
    as_of_ts: str
    horizon_days: int
    prob_up: float = Field(..., ge=0.0, le=1.0)
    prob_down: float = Field(..., ge=0.0, le=1.0)
    prob_flat: float = Field(..., ge=0.0, le=1.0)
    expected_return: float
    return_ci_low: float
    return_ci_high: float
    confidence: float = Field(..., ge=0.0, le=1.0)
    risk_score: float = Field(..., ge=0.0, le=1.0)
    suggested_stop_loss_pct: float
    suggested_take_profit_pct: float
    recommended_action: str
    position_size_pct: float
    top_contributing_factors: List[ContributingFactor]
    explanation: str
    model_version: str
    regime: str

    @model_validator(mode="after")
    def _probs_sum_to_one(self) -> "PredictionResponse":
        total = self.prob_up + self.prob_down + self.prob_flat
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"prob_up+prob_down+prob_flat must sum to 1.0 (got {total})")
        if self.return_ci_low > self.return_ci_high:
            raise ValueError("return_ci_low must be <= return_ci_high")
        return self
