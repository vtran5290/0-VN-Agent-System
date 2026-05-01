"""Logging setup for weekly update pipeline."""
from __future__ import annotations

import logging
import sys
from pathlib import Path


def setup_logging(log_dir: Path | None = None, level: int = logging.INFO) -> logging.Logger:
    """Configure root logger; optionally add file handler to log_dir."""
    log = logging.getLogger("weekly_update")
    log.setLevel(level)
    if not log.handlers:
        h = logging.StreamHandler(sys.stdout)
        h.setLevel(level)
        log.addHandler(h)
    if log_dir:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_dir / "weekly_update.log", encoding="utf-8")
        fh.setLevel(level)
        log.addHandler(fh)
    return log
