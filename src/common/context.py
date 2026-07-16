"""Structured logging + correlation-id context propagation (item 5 / logging)."""
from __future__ import annotations

import contextvars
import logging
import sys
from typing import Optional

try:
    import structlog
    _HAVE_STRUCTLOG = True
except ImportError:  # pragma: no cover
    _HAVE_STRUCTLOG = False

# Per-request correlation id, propagated across calls in a single process/async task.
correlation_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "correlation_id", default=None
)


def set_correlation_id(cid: Optional[str]) -> None:
    correlation_id.set(cid)


def get_correlation_id() -> Optional[str]:
    return correlation_id.get()


def configure_logging(level: str = "INFO", json_logs: bool = True) -> None:
    """Configure structlog JSON output (stdout). No secrets should ever be logged."""
    if not _HAVE_STRUCTLOG:
        logging.basicConfig(level=getattr(logging, level, logging.INFO))
        return
    timestamper = structlog.processors.TimeStamper(fmt="iso")
    shared = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.add_log_level,
        timestamper,
    ]
    if json_logs:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()
    structlog.configure(
        processors=shared + [renderer],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level, logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "quant"):
    if _HAVE_STRUCTLOG:
        return structlog.get_logger(name)
    return logging.getLogger(name)
