"""Idempotent daily run lock and manifest."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.trading.config import LiveTradingConfig
from src.trading.models import OrderState
from src.trading.util.timeutil import utc_now_iso


@dataclass
class RunManifest:
    date: str
    mode: str
    account_id: str = ""
    status: str = "STARTED"  # STARTED | COMPLETED | FAILED
    started_at: str = ""
    completed_at: str = ""
    scan_file: str = ""
    scan_hash: str = ""
    config_hash: str = ""
    data_health_status: str = ""
    intent_count: int = 0
    proposal_count: int = 0
    orders_submitted: int = 0
    paper_fills: int = 0
    kill_switch_status: str = ""
    reconciliation_status: str = ""
    error: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class RunLockError(RuntimeError):
    pass


class DailyRunLock:
    def __init__(self, config: LiveTradingConfig):
        self.config = config
        self.locks_dir = config.live_dir / "run_locks"
        self.manifests_dir = config.live_dir / "run_manifests"
        self.locks_dir.mkdir(parents=True, exist_ok=True)
        self.manifests_dir.mkdir(parents=True, exist_ok=True)

    def _account_suffix(self, account_id: str) -> str:
        return f"_{account_id}" if account_id else ""

    def _lock_path(self, date: str, mode: str, account_id: str = "") -> Path:
        aid = account_id or getattr(self.config, "account_id", "") or ""
        return self.locks_dir / f"{date.replace('-', '')}_{mode}{self._account_suffix(aid)}.lock"

    def _manifest_path(self, date: str, mode: str, account_id: str = "") -> Path:
        aid = account_id or getattr(self.config, "account_id", "") or ""
        return self.manifests_dir / f"run_{date.replace('-', '')}_{mode}{self._account_suffix(aid)}.json"

    def load_manifest(self, date: str, mode: str, account_id: str = "") -> Optional[RunManifest]:
        p = self._manifest_path(date, mode, account_id)
        if not p.exists():
            return None
        data = json.loads(p.read_text(encoding="utf-8"))
        return RunManifest(**{k: data[k] for k in RunManifest.__dataclass_fields__ if k in data})

    def _save_manifest(self, manifest: RunManifest) -> Path:
        p = self._manifest_path(manifest.date, manifest.mode)
        p.write_text(json.dumps(manifest.to_dict(), indent=2), encoding="utf-8")
        return p

    def _has_open_submitted_orders(self, date: str) -> bool:
        open_states = {
            OrderState.ORDER_SUBMITTED.value,
            OrderState.PARTIALLY_FILLED.value,
        }
        for f in self.config.orders_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                if data.get("state") in open_states:
                    ad = data.get("proposal", {}).get("signal", {}).get("asof_date", "")
                    if ad[:10] == date[:10]:
                        return True
            except (json.JSONDecodeError, KeyError):
                continue
        return False

    def acquire(self, date: str, mode: str, force: bool = False, account_id: str = "") -> RunManifest:
        aid = account_id or getattr(self.config, "account_id", "") or ""
        lock_path = self._lock_path(date, mode, aid)
        existing = self.load_manifest(date, mode, aid)

        if lock_path.exists():
            raise RunLockError(f"Run lock exists (STARTED): {lock_path}")

        if existing and existing.status == "COMPLETED" and not force:
            raise RunLockError(
                f"Run already COMPLETED for {date} mode={mode}. Use --force to rerun."
            )

        if force and self._has_open_submitted_orders(date):
            raise RunLockError(
                "Cannot --force: open ORDER_SUBMITTED/PARTIALLY_FILLED orders exist for this date"
            )

        manifest = RunManifest(
            date=date[:10],
            mode=mode,
            account_id=aid,
            status="STARTED",
            started_at=utc_now_iso(),
        )
        # atomic lock create
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, manifest.started_at.encode())
            os.close(fd)
        except FileExistsError:
            raise RunLockError(f"Concurrent run lock: {lock_path}") from None

        self._save_manifest(manifest)
        return manifest

    def complete(self, manifest: RunManifest, **fields: Any) -> Path:
        manifest.status = "COMPLETED"
        manifest.completed_at = utc_now_iso()
        for k, v in fields.items():
            if hasattr(manifest, k):
                setattr(manifest, k, v)
        self._save_manifest(manifest)
        lock_path = self._lock_path(manifest.date, manifest.mode, manifest.account_id)
        if lock_path.exists():
            lock_path.unlink()
        return self._manifest_path(manifest.date, manifest.mode, manifest.account_id)

    def fail(self, manifest: RunManifest, error: str) -> Path:
        manifest.status = "FAILED"
        manifest.completed_at = utc_now_iso()
        manifest.error = error
        self._save_manifest(manifest)
        lock_path = self._lock_path(manifest.date, manifest.mode, manifest.account_id)
        if lock_path.exists():
            lock_path.unlink()
        return self._manifest_path(manifest.date, manifest.mode)
