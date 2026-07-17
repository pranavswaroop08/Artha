"""LLM client interface for the NLP pipeline (news parsing, explainability).

Provider-agnostic: `MockLLMClient` (deterministic, dev/CI, zero-credential) and
`KimiLLMClient` (Moonshot AI, OpenAI-SDK compatible) behind a common Protocol.

PIT WARNING: any feature derived from parsed news MUST be stamped with
`as_of_ts` = the article's publish timestamp before it enters the feature store,
so it flows through the same point-in-time gate as market data. LLM-derived
features are a classic leakage vector (revised/backfilled articles).
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from ..common.context import get_logger

logger = get_logger(__name__)

KIMI_SYSTEM_PROMPT = """\
You are an expert quantitative financial analyst specializing in the Indian \
stock market (NSE/BSE). Analyze the financial news text and extract structured, \
point-in-time features for a machine learning model.

For EACH article, extract:
1. mentioned_symbols: list of NSE/BSE tickers explicitly mentioned or strongly \
implied (e.g. "Reliance" -> "RELIANCE.NS"). Empty list if none.
2. overall_sentiment: float from -1.0 (extremely bearish) to 1.0 (extremely \
bullish). 0.0 = neutral or irrelevant.
3. impact_type: one of ["EARNINGS", "MACRO", "REGULATORY", "CORPORATE_ACTION", \
"SECTOR_TREND", "ANALYST_RATING", "OTHER"].
4. time_horizon: one of ["INTRADAY", "SHORT_TERM", "MEDIUM_TERM", "LONG_TERM"].
5. summary: one concise sentence on the key price-relevant takeaway.

Return ONLY a valid JSON object of the form {"results": [ ... ]} where results \
is an array with one object per article, in order. No markdown, no prose.
"""

# Canonical schema keys every client must return per article.
REQUIRED_KEYS = frozenset(
    {"mentioned_symbols", "overall_sentiment", "impact_type", "time_horizon", "summary"}
)

_NEUTRAL = {
    "mentioned_symbols": [],
    "overall_sentiment": 0.0,
    "impact_type": "OTHER",
    "time_horizon": "INTRADAY",
    "summary": "No specific stock impact detected.",
}


@runtime_checkable
class LLMClient(Protocol):
    def parse_news(self, news_texts: List[str]) -> List[Dict[str, Any]]:
        ...


class MockLLMClient:
    """Deterministic mock for dev/CI. Simple keyword heuristics, no network."""

    def parse_news(self, news_texts: List[str]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for text in news_texts:
            low = text.lower()
            if "reliance" in low:
                results.append({
                    "mentioned_symbols": ["RELIANCE.NS"],
                    "overall_sentiment": 0.75,
                    "impact_type": "CORPORATE_ACTION",
                    "time_horizon": "MEDIUM_TERM",
                    "summary": "Reliance announces strong subscriber additions.",
                })
            elif "tcs" in low or "infosys" in low:
                results.append({
                    "mentioned_symbols": ["TCS.NS" if "tcs" in low else "INFY.NS"],
                    "overall_sentiment": 0.3,
                    "impact_type": "EARNINGS",
                    "time_horizon": "SHORT_TERM",
                    "summary": "IT major reports quarterly results.",
                })
            else:
                results.append(dict(_NEUTRAL))
        return results


class KimiLLMClient:
    """Moonshot AI (Kimi) client via the OpenAI-compatible SDK.

    The OpenAI client is created lazily on first use so importing this module
    never requires network/creds. For tests, inject a fake via `client=`.
    """

    def __init__(
        self,
        api_key: Optional[str],
        model: str = "moonshot-v1-8k",
        base_url: str = "https://api.moonshot.cn/v1",
        client: Any = None,
    ):
        if not api_key and client is None:
            raise ValueError("Kimi API key is missing.")
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self._client = client  # injectable for tests
        logger.info("kimi_client_init", model=model)

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI  # lazy import

            self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        return self._client

    def parse_news(self, news_texts: List[str]) -> List[Dict[str, Any]]:
        if not news_texts:
            return []
        batched = "\n---\n".join(
            f"Article {i + 1}: {t}" for i, t in enumerate(news_texts)
        )
        resp = self._get_client().chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": KIMI_SYSTEM_PROMPT},
                {"role": "user", "content": batched},
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content
        return self._parse_response(content, expected=len(news_texts))

    @staticmethod
    def _parse_response(content: str, expected: int) -> List[Dict[str, Any]]:
        """Parse + validate the model's JSON, degrading gracefully to neutral."""
        try:
            data = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            logger.warning("kimi_bad_json_falling_back_neutral")
            return [dict(_NEUTRAL) for _ in range(expected)]
        results = data.get("results", data) if isinstance(data, dict) else data
        if not isinstance(results, list):
            results = [results]
        cleaned: List[Dict[str, Any]] = []
        for item in results:
            if isinstance(item, dict) and REQUIRED_KEYS.issubset(item):
                cleaned.append(item)
            else:
                merged = dict(_NEUTRAL)
                if isinstance(item, dict):
                    merged.update({k: v for k, v in item.items() if k in REQUIRED_KEYS})
                cleaned.append(merged)
        return cleaned


def get_llm_client(
    provider: str = "mock", api_key: Optional[str] = None, **kwargs: Any
) -> LLMClient:
    """Factory: 'mock' (default) or 'kimi'."""
    if provider == "mock":
        return MockLLMClient()
    if provider == "kimi":
        return KimiLLMClient(api_key=api_key, **kwargs)
    raise ValueError(f"Unknown LLM provider: {provider}")
