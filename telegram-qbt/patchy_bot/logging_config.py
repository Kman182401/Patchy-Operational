"""JSON-structured log formatter for journalctl/jq integration."""

from __future__ import annotations

import json
import logging
from typing import Any


class _JsonFormatter(logging.Formatter):
    """Optional structured JSON log formatter.

    Activated by setting LOG_FORMAT=json in the environment.
    Each log record becomes a single-line JSON object suitable for
    ingestion by log aggregators or ad-hoc querying with jq.

    Usage:
        journalctl -u telegram-qbt-bot -o cat | jq 'select(.level=="ERROR")'
    """

    def format(self, record: logging.LogRecord) -> str:
        obj: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            obj["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            obj["stack_info"] = self.formatStack(record.stack_info)
        # Include any extra fields attached via logger.info("...", extra={...})
        skip = {
            "name", "msg", "args", "levelname", "levelno", "pathname",
            "filename", "module", "exc_info", "exc_text", "stack_info",
            "lineno", "funcName", "created", "msecs", "relativeCreated",
            "thread", "threadName", "processName", "process", "message",
            "taskName",
        }
        for key, value in record.__dict__.items():
            if key not in skip:
                try:
                    json.dumps(value)  # only include JSON-serializable extras
                    obj[key] = value
                except (TypeError, ValueError):
                    pass
        return json.dumps(obj, ensure_ascii=False)

