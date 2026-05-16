"""Reconciliation — expected vs broker state."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from src.trading.brokers.base import BaseBroker
from src.trading.config import LiveTradingConfig, TradingConfig
from src.trading.models import ManagedOrder, OrderState
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.trading.oms.order_manager import OrderManager
from src.trading.reconciliation.baseline import baseline_positions_qty, load_latest_baseline
from src.trading.util.timeutil import utc_now_iso


@dataclass
class ReconciliationReport:
    asof_date: str
    missing_fills: List[Dict[str, Any]] = field(default_factory=list)
    partial_fills: List[Dict[str, Any]] = field(default_factory=list)
    unexpected_positions: List[Dict[str, Any]] = field(default_factory=list)
    cash_mismatch: Dict[str, Any] = field(default_factory=dict)
    duplicate_orders: List[Dict[str, Any]] = field(default_factory=list)
    rejected_orders: List[Dict[str, Any]] = field(default_factory=list)
    generated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def has_issues(self) -> bool:
        return bool(
            self.missing_fills
            or self.partial_fills
            or self.unexpected_positions
            or self.cash_mismatch.get("mismatch")
            or self.duplicate_orders
        )


class Reconciler:
    def __init__(self, config: TradingConfig, broker: BaseBroker, order_manager: "OrderManager"):
        self.config = config
        self.broker = broker
        self.om = order_manager

    def _oms_delta_positions(self, orders: List[ManagedOrder], after_date: Optional[str] = None) -> Dict[str, int]:
        expected: Dict[str, int] = {}
        for mo in orders:
            if mo.state != OrderState.FILLED:
                continue
            ad = mo.proposal.signal.asof_date[:10]
            if after_date and ad <= after_date:
                continue
            sym = mo.proposal.signal.symbol
            side = mo.proposal.signal.side.upper()
            qty = mo.proposal.signal.quantity
            if side == "BUY":
                expected[sym] = expected.get(sym, 0) + qty
            elif side == "SELL":
                expected[sym] = expected.get(sym, 0) - qty
        return expected

    def run(self, asof_date: str) -> ReconciliationReport:
        orders = self.om.load_all_orders()
        report = ReconciliationReport(asof_date=asof_date, generated_at=utc_now_iso())

        for mo in orders:
            if mo.state == OrderState.ORDER_SUBMITTED:
                report.missing_fills.append(
                    {"idempotency_key": mo.idempotency_key, "symbol": mo.proposal.signal.symbol}
                )
            if mo.state == OrderState.PARTIALLY_FILLED:
                report.partial_fills.append(
                    {"idempotency_key": mo.idempotency_key, "symbol": mo.proposal.signal.symbol}
                )
            if mo.state in (OrderState.REJECTED_BY_RISK, OrderState.BROKER_REJECTED, OrderState.REJECTED_AT_EXECUTION):
                report.rejected_orders.append(
                    {
                        "idempotency_key": mo.idempotency_key,
                        "state": mo.state.value,
                        "reasons": mo.risk_verdict.reasons if mo.risk_verdict else [],
                    }
                )

        keys = [mo.idempotency_key for mo in orders]
        seen: set[str] = set()
        for k in keys:
            if k in seen:
                report.duplicate_orders.append({"idempotency_key": k})
            seen.add(k)

        baseline = load_latest_baseline(self.config, asof_date)
        base_qty = baseline_positions_qty(baseline)
        oms_delta = self._oms_delta_positions(
            orders, after_date=baseline.get("asof_date") if baseline else None
        )
        expected = dict(base_qty)
        for sym, dq in oms_delta.items():
            expected[sym] = expected.get(sym, 0) + dq

        broker_pos = {p["symbol"]: int(p["quantity"]) for p in self.broker.get_positions()}

        for sym, exp_qty in expected.items():
            bro_qty = broker_pos.get(sym, 0)
            if exp_qty != bro_qty:
                report.unexpected_positions.append(
                    {
                        "symbol": sym,
                        "expected_qty": exp_qty,
                        "broker_qty": bro_qty,
                        "type": "mismatch",
                    }
                )

        for sym, bro_qty in broker_pos.items():
            if sym not in expected and bro_qty != 0:
                report.unexpected_positions.append(
                    {
                        "symbol": sym,
                        "expected_qty": 0,
                        "broker_qty": bro_qty,
                        "type": "unexpected_broker_position",
                    }
                )

        return report

    def save_report(self, report: ReconciliationReport) -> Path:
        self.config.reconciliation_dir.mkdir(parents=True, exist_ok=True)
        path = self.config.reconciliation_dir / f"recon_{report.asof_date}.json"
        path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
        return path

    def save_live_status(self, report: ReconciliationReport) -> Path:
        live_dir = self.config.live_dir if hasattr(self.config, "live_dir") else self.config.data_root / "live"
        live_dir.mkdir(parents=True, exist_ok=True)
        block = report.has_issues()
        status = {
            "asof_date": report.asof_date,
            "BLOCK_NEW_ORDERS": block,
            "has_issues": block,
            "generated_at": report.generated_at,
        }
        csv_rows = []
        for item in report.unexpected_positions:
            csv_rows.append({**item, "issue_type": item.get("type")})
        if csv_rows:
            pd.DataFrame(csv_rows).to_csv(
                live_dir / f"reconciliation_{report.asof_date.replace('-', '')}.csv",
                index=False,
            )
        status_path = live_dir / "reconciliation_status.json"
        status_path.write_text(json.dumps(status, indent=2), encoding="utf-8")
        return status_path
