from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # type: ignore[override]
        payload = {
            "ts": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "name": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(debug: bool = False, to_stderr: bool = True) -> None:
    level = logging.DEBUG if debug else logging.INFO
    logging.captureWarnings(True)

    root = logging.getLogger()
    root.setLevel(level)
    for h in list(root.handlers):
        root.removeHandler(h)

    # Optional stderr handler (disabled for TUI run to avoid overlay)
    if to_stderr:
        stderr = logging.StreamHandler()
        stderr.setLevel(level)
        stderr.setFormatter(JsonFormatter())
        root.addHandler(stderr)

    # file handler
    log_dir = Path(os.getenv("XDG_CACHE_HOME", Path.home() / ".cache")) / "polly"
    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_dir / "polly.log")
    file_handler.setLevel(level)
    file_handler.setFormatter(JsonFormatter())
    root.addHandler(file_handler)


