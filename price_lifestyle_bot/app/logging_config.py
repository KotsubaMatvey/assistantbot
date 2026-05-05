from __future__ import annotations

import logging
import sys

try:
    import structlog
except ImportError:
    structlog = None  # type: ignore[assignment]


class PlainLogger:
    def __init__(self, name: str) -> None:
        self._logger = logging.getLogger(name)

    def info(self, event: str, **kwargs: object) -> None:
        self._logger.info("%s %s", event, kwargs)

    def warning(self, event: str, **kwargs: object) -> None:
        self._logger.warning("%s %s", event, kwargs)

    def exception(self, event: str, **kwargs: object) -> None:
        self._logger.exception("%s %s", event, kwargs)


def configure_logging() -> None:
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=logging.INFO)
    if structlog is None:
        return
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str):
    if structlog is None:
        return PlainLogger(name)
    return structlog.get_logger(name)
