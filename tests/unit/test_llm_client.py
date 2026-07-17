"""Tests for the LLM client interface."""
from __future__ import annotations

import json

import pytest

from src.nlp.llm_client import (
    KimiLLMClient,
    MockLLMClient,
    REQUIRED_KEYS,
    get_llm_client,
)


def test_mock_llm_client_returns_valid_schema():
    client = MockLLMClient()
    news = ["Reliance industries announces bonus shares.", "Generic market news today."]
    results = client.parse_news(news)
    assert len(results) == 2
    assert results[0]["mentioned_symbols"] == ["RELIANCE.NS"]
    assert isinstance(results[0]["overall_sentiment"], float)
    # Every result carries the full canonical schema.
    for r in results:
        assert REQUIRED_KEYS.issubset(r)


def test_factory_returns_mock_client():
    assert isinstance(get_llm_client(provider="mock"), MockLLMClient)


def test_factory_returns_kimi_client():
    client = get_llm_client(provider="kimi", api_key="fake_key")
    assert isinstance(client, KimiLLMClient)


def test_factory_unknown_provider_raises():
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        get_llm_client(provider="gpt5")


def test_kimi_client_requires_api_key():
    with pytest.raises(ValueError, match="API key is missing"):
        KimiLLMClient(api_key=None)


class _FakeChoice:
    def __init__(self, content):
        self.message = type("M", (), {"content": content})


class _FakeCompletions:
    def __init__(self, content):
        self._content = content
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return type("R", (), {"choices": [_FakeChoice(self._content)]})


class _FakeOpenAI:
    def __init__(self, content):
        self.chat = type("C", (), {"completions": _FakeCompletions(content)})


def test_kimi_parses_real_response_shape_via_injected_client():
    """Exercises the ACTUAL prod parse path with an injected fake OpenAI client."""
    payload = json.dumps({
        "results": [{
            "mentioned_symbols": ["TCS.NS"],
            "overall_sentiment": 0.5,
            "impact_type": "EARNINGS",
            "time_horizon": "SHORT_TERM",
            "summary": "TCS beats estimates.",
        }]
    })
    fake = _FakeOpenAI(payload)
    client = KimiLLMClient(api_key="k", client=fake)
    out = client.parse_news(["TCS Q1 results beat estimates"])
    assert len(out) == 1
    assert out[0]["mentioned_symbols"] == ["TCS.NS"]
    assert out[0]["impact_type"] == "EARNINGS"
    # System prompt + JSON response_format actually sent.
    kw = fake.chat.completions.last_kwargs
    assert kw["response_format"] == {"type": "json_object"}
    assert kw["messages"][0]["role"] == "system"


def test_kimi_bad_json_falls_back_to_neutral():
    client = KimiLLMClient(api_key="k", client=_FakeOpenAI("not json at all"))
    out = client.parse_news(["a", "b"])
    assert len(out) == 2
    assert all(r["impact_type"] == "OTHER" for r in out)


def test_kimi_empty_input_returns_empty():
    client = KimiLLMClient(api_key="k", client=_FakeOpenAI("{}"))
    assert client.parse_news([]) == []
