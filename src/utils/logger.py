"""Structured (JSON-line) logging with secret redaction."""
from __future__ import annotations

import json
import logging
import os
import re
import sys

_SECRET = re.compile(r"(sk-ant-[A-Za-z0-9_\-]+|api[_-]?key\s*[=:]\s*\S+)", re.IGNORECASE)


def redact(text: str) -> str:
    return _SECRET.sub("[REDACTED]", text)


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            {
                "time": self.formatTime(record),
                "level": record.levelname,
                "logger": record.name,
                "message": redact(record.getMessage()),
            }
        )


def get_logger(name: str = "lessongen") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(_JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
        logger.propagate = False
    return logger
