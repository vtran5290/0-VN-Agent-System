"""Idempotency store for order deduplication."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from src.trading.models import ManagedOrder


class IdempotencyStore:
    def __init__(self, orders_dir: Path):
        self.orders_dir = orders_dir
        self.orders_dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, key: str) -> Path:
        safe = key.replace("|", "_").replace("/", "_")
        return self.orders_dir / f"{safe}.json"

    def exists(self, key: str) -> bool:
        return self.path_for(key).exists()

    def load(self, key: str) -> Optional[ManagedOrder]:
        p = self.path_for(key)
        if not p.exists():
            return None
        return ManagedOrder.from_dict(json.loads(p.read_text(encoding="utf-8")))

    def save(self, order: ManagedOrder) -> None:
        p = self.path_for(order.idempotency_key)
        p.write_text(json.dumps(order.to_dict(), indent=2), encoding="utf-8")

    def list_keys(self) -> list[str]:
        return [p.stem for p in self.orders_dir.glob("*.json")]
