"""Tests for the Feast feature-store scaffold (PIT-compliant EOD view).

These validate that Feast can load our repo config, register the entity and
feature view, and that the point-in-time timestamp columns are wired correctly.

Requires the `feast` package. Skipped automatically if it is installed not.

Each test builds an isolated copy of the feature repo (with a temp registry
path) so parallel/sequential runs don't collide on disk.
"""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import pytest

feast_installed = True
try:
    from feast import FeatureStore
except ImportError:  # pragma: no cover
    feast_installed = False

REPO_PATH = Path(__file__).parent.parent.parent / "feature_store" / "feature_repo"


def _store(tmp_path: Path) -> FeatureStore:
    os.environ.setdefault("FEAST_USAGE", "False")
    # Copy the real repo into a temp dir. Each test's tmp_path is unique, so
    # the relative data/registry.db + data/online_store.db are automatically
    # isolated per test (no path rewriting needed).
    work = tmp_path / "repo"
    shutil.copytree(REPO_PATH, work)
    (work / "data").mkdir(parents=True, exist_ok=True)
    (work / "data" / "offline").mkdir(parents=True, exist_ok=True)
    store = FeatureStore(repo_path=str(work))
    import importlib.util

    spec = importlib.util.spec_from_file_location("artha_features", work / "features.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    store.apply([mod.symbol_entity, mod.eod_market_data_view])
    return store


@pytest.mark.skipif(not feast_installed, reason="feast package not installed")
def test_feature_store_applies_and_registers(tmp_path):
    """Apply the repo and confirm entity + feature view are registered."""
    store = _store(tmp_path)

    entities = {e.name for e in store.list_entities()}
    assert "symbol" in entities

    views = {fv.name for fv in store.list_feature_views()}
    assert "eod_market_data" in views


@pytest.mark.skipif(not feast_installed, reason="feast package not installed")
def test_feature_view_pit_columns(tmp_path):
    """PIT columns must be pinned: event_ts (event) + as_of_ts (disclosure)."""
    store = _store(tmp_path)
    fv = store.get_feature_view("eod_market_data")
    src = fv.batch_source
    assert src.timestamp_field == "event_ts"
    assert src.created_timestamp_column == "as_of_ts"
