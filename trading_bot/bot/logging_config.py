from __future__ import annotations

import contextvars
import json
import logging
import os
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any


TRACE_ID: contextvars.ContextVar[str | None] = contextvars.ContextVar("trace_id", default=None)


class _TraceIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        trace_id = TRACE_ID.get()
        if trace_id and not hasattr(record, "trace_id"):
            setattr(record, "trace_id", trace_id)
        return True


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        for key in ("trace_id", "event", "request", "response", "error", "context"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(log_path: str | os.PathLike, level: int = logging.INFO) -> None:
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(level)

    # Avoid duplicate handlers if setup called multiple times.
    if any(isinstance(h, RotatingFileHandler) for h in root.handlers):
        return

    handler = RotatingFileHandler(
        filename=str(log_path),
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setLevel(level)
    handler.setFormatter(_JsonFormatter())
    handler.addFilter(_TraceIdFilter())
    root.addHandler(handler)

    # Keep console concise; file is the source of truth.
    console = logging.StreamHandler()
    console.setLevel(level)
    console.setFormatter(logging.Formatter("%(levelname)s %(name)s - %(message)s"))
    console.addFilter(_TraceIdFilter())
    root.addHandler(console)
