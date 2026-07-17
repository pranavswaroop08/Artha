"""Tests for Prometheus monitoring integration."""
from __future__ import annotations

from fastapi.testclient import TestClient
from prometheus_client.parser import text_string_to_metric_families

from src.serve.app import app

client = TestClient(app)


def _counter_total(metrics_text: str, name: str) -> float:
    """Sum all samples of a counter across label sets (real value, not substrings)."""
    total = 0.0
    for fam in text_string_to_metric_families(metrics_text):
        if fam.name == name:
            for s in fam.samples:
                if s.name == name + "_total":
                    total += s.value
    return total


def test_metrics_endpoint_exists():
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "artha_predict_requests_total" in r.text


def test_prediction_increments_request_counter():
    before = _counter_total(client.get("/metrics").text, "artha_predict_requests")
    client.post("/predict", json={"symbol": "TEST", "as_of_ts": "2026-07-16T00:00:00Z"})
    after = _counter_total(client.get("/metrics").text, "artha_predict_requests")
    assert after == before + 1.0


def test_latency_and_confidence_histograms_recorded():
    client.post("/predict", json={"symbol": "RELIANCE", "as_of_ts": "2026-07-16T00:00:00Z"})
    text = client.get("/metrics").text
    assert "artha_predict_latency_seconds_bucket" in text
    assert "artha_prediction_confidence_bucket" in text
    # Confidence histogram has at least one observation.
    count = 0.0
    for fam in text_string_to_metric_families(text):
        if fam.name == "artha_prediction_confidence":
            for s in fam.samples:
                if s.name == "artha_prediction_confidence_count":
                    count = s.value
    assert count >= 1.0


def test_health_still_works_with_middleware():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "healthy"}
