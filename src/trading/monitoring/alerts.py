"""Alert hooks — mock implementation for v1."""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


class AlertHook(ABC):
    @abstractmethod
    def send(self, level: str, message: str, payload: Optional[Dict[str, Any]] = None) -> None:
        pass


class MockAlertHook(AlertHook):
    def __init__(self, log_path: Optional[Path] = None):
        self.log_path = log_path
        self.events: list[Dict[str, Any]] = []

    def send(self, level: str, message: str, payload: Optional[Dict[str, Any]] = None) -> None:
        event = {
            "level": level,
            "message": message,
            "payload": payload or {},
            "ts": datetime.utcnow().isoformat() + "Z",
        }
        self.events.append(event)
        if self.log_path:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")
