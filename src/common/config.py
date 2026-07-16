"""Central configuration loader (Hydra-style via OmegaConf).

Resolves the merged config from configs/ with environment overlays, and pulls
secrets from environment variables (never committed). This is the single source
of truth for paths, DB DSNs, and provider settings.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

try:
    from omegaconf import DictConfig, OmegaConf
except ImportError:  # pragma: no cover - graceful when omegaconf absent
    OmegaConf = None  # type: ignore
    DictConfig = Any  # type: ignore

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "configs"


def _read_yaml(path: Path) -> dict:
    if OmegaConf is not None and path.exists():
        return OmegaConf.to_container(OmegaConf.load(path), resolve=True)  # type: ignore
    # Fallback minimal config so the project imports without deps installed yet.
    return {}


@lru_cache(maxsize=1)
def load_config(env: str | None = None) -> dict:
    """Load merged config. env overrides: dev | staging | prod (default dev)."""
    env = env or os.getenv("QUANT_ENV", "dev")
    base = _read_yaml(CONFIG_DIR / "config.yaml")
    overlay = _read_yaml(CONFIG_DIR / f"config.{env}.yaml")
    merged = _deep_merge(base, overlay)
    merged.setdefault("env", env)
    merged.setdefault("project_root", str(PROJECT_ROOT))
    return merged


def _deep_merge(a: dict, b: dict) -> dict:
    out = dict(a)
    for k, v in b.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def secret(key: str, default: str | None = None) -> str | None:
    """Read a secret from environment (or .env at runtime)."""
    return os.getenv(key, default)
