"""SQLite-backed persistent order journal for crash-safe submission tracking."""
from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.trading.util.timeutil import utc_now_iso

logger = logging.getLogger(__name__)


class JournalStatus(str, Enum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class DuplicateOrderError(RuntimeError):
    """Raised when re-submitting an order already SUBMITTED or FILLED in the journal."""


class OrphanOrderError(RuntimeError):
    """Raised when a PENDING journal row exists — operator reconciliation required."""


@dataclass
class JournalEntry:
    order_id: str
    symbol: str
    action: str
    qty: int
    price: float
    status: JournalStatus
    broker_ref: str = ""
    created_at: str = ""
    updated_at: str = ""
    raw_broker_response: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "action": self.action,
            "qty": self.qty,
            "price": self.price,
            "status": self.status.value,
            "broker_ref": self.broker_ref,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "raw_broker_response": self.raw_broker_response,
        }


class OrderJournal:
    """Append-only order event journal with atomic SQLite writes (WAL mode)."""

    _SCHEMA = """
    CREATE TABLE IF NOT EXISTS order_events (
        order_id TEXT PRIMARY KEY,
        symbol TEXT NOT NULL,
        action TEXT NOT NULL,
        qty INTEGER NOT NULL,
        price REAL NOT NULL,
        status TEXT NOT NULL,
        broker_ref TEXT DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        raw_broker_response TEXT DEFAULT ''
    );
    CREATE INDEX IF NOT EXISTS idx_order_events_status ON order_events(status);
    CREATE INDEX IF NOT EXISTS idx_order_events_created ON order_events(created_at);
    """

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(self._SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def _row_to_entry(self, row: tuple) -> JournalEntry:
        return JournalEntry(
            order_id=row[0],
            symbol=row[1],
            action=row[2],
            qty=int(row[3]),
            price=float(row[4]),
            status=JournalStatus(row[5]),
            broker_ref=row[6] or "",
            created_at=row[7],
            updated_at=row[8],
            raw_broker_response=row[9] or "",
        )

    def get(self, order_id: str) -> Optional[JournalEntry]:
        cur = self._conn.execute(
            "SELECT order_id, symbol, action, qty, price, status, broker_ref, "
            "created_at, updated_at, raw_broker_response "
            "FROM order_events WHERE order_id = ?",
            (order_id,),
        )
        row = cur.fetchone()
        return self._row_to_entry(row) if row else None

    def assert_can_submit(self, order_id: str) -> None:
        existing = self.get(order_id)
        if not existing:
            return
        if existing.status in (JournalStatus.SUBMITTED, JournalStatus.FILLED):
            raise DuplicateOrderError(
                f"Order {order_id} already {existing.status.value} in journal"
            )
        if existing.status == JournalStatus.PENDING:
            raise OrphanOrderError(
                f"Order {order_id} is PENDING in journal — operator reconciliation required"
            )

    def write_pending(
        self,
        order_id: str,
        *,
        symbol: str,
        action: str,
        qty: int,
        price: float,
    ) -> JournalEntry:
        self.assert_can_submit(order_id)
        now = utc_now_iso()
        self._conn.execute(
            "INSERT INTO order_events "
            "(order_id, symbol, action, qty, price, status, broker_ref, "
            "created_at, updated_at, raw_broker_response) "
            "VALUES (?, ?, ?, ?, ?, ?, '', ?, ?, '')",
            (order_id, symbol.upper(), action.upper(), qty, price, JournalStatus.PENDING.value, now, now),
        )
        self._conn.commit()
        return self.get(order_id)  # type: ignore[return-value]

    def mark_submitted(
        self,
        order_id: str,
        broker_ref: str,
        raw_response: Optional[Dict[str, Any]] = None,
    ) -> None:
        now = utc_now_iso()
        raw_json = json.dumps(raw_response or {})
        self._conn.execute(
            "UPDATE order_events SET status = ?, broker_ref = ?, updated_at = ?, "
            "raw_broker_response = ? WHERE order_id = ?",
            (JournalStatus.SUBMITTED.value, broker_ref, now, raw_json, order_id),
        )
        self._conn.commit()

    def mark_filled(
        self,
        order_id: str,
        raw_response: Optional[Dict[str, Any]] = None,
    ) -> None:
        now = utc_now_iso()
        raw_json = json.dumps(raw_response or {})
        self._conn.execute(
            "UPDATE order_events SET status = ?, updated_at = ?, raw_broker_response = ? "
            "WHERE order_id = ?",
            (JournalStatus.FILLED.value, now, raw_json, order_id),
        )
        self._conn.commit()

    def mark_rejected(
        self,
        order_id: str,
        raw_response: Optional[Dict[str, Any]] = None,
    ) -> None:
        now = utc_now_iso()
        raw_json = json.dumps(raw_response or {})
        self._conn.execute(
            "UPDATE order_events SET status = ?, updated_at = ?, raw_broker_response = ? "
            "WHERE order_id = ?",
            (JournalStatus.REJECTED.value, now, raw_json, order_id),
        )
        self._conn.commit()

    def count_submissions_today(self, day_prefix: Optional[str] = None) -> int:
        """Count SUBMITTED + FILLED rows for today (UTC date prefix on created_at)."""
        prefix = day_prefix or utc_now_iso()[:10]
        cur = self._conn.execute(
            "SELECT COUNT(*) FROM order_events "
            "WHERE created_at LIKE ? AND status IN (?, ?)",
            (f"{prefix}%", JournalStatus.SUBMITTED.value, JournalStatus.FILLED.value),
        )
        return int(cur.fetchone()[0])

    def find_recovery_candidates(self) -> List[JournalEntry]:
        cur = self._conn.execute(
            "SELECT order_id, symbol, action, qty, price, status, broker_ref, "
            "created_at, updated_at, raw_broker_response "
            "FROM order_events WHERE status IN (?, ?) ORDER BY created_at",
            (JournalStatus.PENDING.value, JournalStatus.SUBMITTED.value),
        )
        return [self._row_to_entry(row) for row in cur.fetchall()]

    def write_recovery_report(self, report_path: Path, orphans: List[JournalEntry]) -> None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "generated_at": utc_now_iso(),
            "orphan_count": len(orphans),
            "orders": [o.to_dict() for o in orphans],
            "action_required": "Operator must reconcile PENDING/SUBMITTED orders with broker state",
        }
        report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def run_startup_recovery(self, report_path: Path) -> List[JournalEntry]:
        orphans = self.find_recovery_candidates()
        if orphans:
            logger.warning(
                "Order journal recovery: %d PENDING/SUBMITTED orders require operator review",
                len(orphans),
            )
            for entry in orphans:
                logger.warning(
                    "  orphan order_id=%s status=%s symbol=%s broker_ref=%s",
                    entry.order_id,
                    entry.status.value,
                    entry.symbol,
                    entry.broker_ref,
                )
            self.write_recovery_report(report_path, orphans)
        return orphans
