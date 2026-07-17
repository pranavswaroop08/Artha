"""Tests for the finance-aware sentiment scorer (local backend)."""
from __future__ import annotations

from src.nlp.sentiment import LocalSentimentScorer, score_headlines


def test_bullish_headline_positive():
    s = LocalSentimentScorer()
    assert s.score("Stock surges to record high as profits beat estimates") > 0.3
    assert s.score("Shares rally after strong upgrade") > 0.3


def test_bearish_headline_negative():
    s = LocalSentimentScorer()
    assert s.score("Stock plunges as losses mount after profit warning") < -0.3
    assert s.score("Shares crash on fraud probe and downgrade") < -0.3


def test_negation_flips_sign():
    s = LocalSentimentScorer()
    pos = s.score("Company reports profit growth")
    neg = s.score("Company does not report profit growth")
    # Negation should pull the score toward / below neutral.
    assert neg < pos


def test_neutral_headline_near_zero():
    s = LocalSentimentScorer()
    assert abs(s.score("The board met to discuss the agenda")) < 0.2


def test_deterministic_and_batch():
    heads = [
        "Sensex rallies 900 points on strong earnings",
        "Stock crashes after fraud allegation",
        "Company announces routine board meeting",
    ]
    a = score_headlines(heads, provider="local")
    b = score_headlines(heads, provider="local")
    assert a == b
    assert a[0] > 0.2 > a[2] >= -0.2
    assert a[1] < -0.2


def test_empty_input():
    assert score_headlines([], provider="local") == []
