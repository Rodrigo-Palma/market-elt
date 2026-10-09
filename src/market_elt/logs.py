"""Structured logging: one JSON object per line on stderr."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

LOGGER_NAME = "market_elt"


class JsonFormatter(logging.Formatter):
    """Render a record as ``{"ts", "level", "event", **fields}``.

    Structured values travel in ``extra={"fields": {...}}``.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "event": record.getMessage(),
        }
        payload.update(getattr(record, "fields", {}))
        if record.exc_info:
            payload["error"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def get_logger() -> logging.Logger:
    """The package logger, with a JSON handler attached once."""
    logger = logging.getLogger(LOGGER_NAME)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger
