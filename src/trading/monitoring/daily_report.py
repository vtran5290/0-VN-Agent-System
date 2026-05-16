"""Daily trading report — signals, risk, positions, exposure."""
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List

import pandas as pd

from src.trading.brokers.base import BaseBroker
from src.trading.config import LiveTradingConfig, TradingConfig
from src.trading.models import ManagedOrder, OrderState, load_proposals, proposals_path
from src.trading.reconciliation.reconciler import ReconciliationReport
from src.trading.util.timeutil import utc_now_iso

if TYPE_CHECKING:
    from src.trading.oms.order_manager import OrderManager


def filter_orders_by_date(orders: List[ManagedOrder], asof_date: str) -> List[ManagedOrder]:
    ad = asof_date[:10]
    return [o for o in orders if o.proposal.signal.asof_date[:10] == ad]


class DailyReportBuilder:
    def __init__(
        self,
        config: TradingConfig,
        broker: BaseBroker,
        order_manager: "OrderManager",
    ):
        self.config = config
        self.broker = broker
        self.om = order_manager

    def build(
        self,
        asof_date: str,
        recon: ReconciliationReport | None = None,
    ) -> Dict[str, Any]:
        proposals = load_proposals(proposals_path(self.config.data_root, asof_date))
        all_orders = self.om.load_all_orders()
        daily_orders = filter_orders_by_date(all_orders, asof_date)
        rejected_daily = [o for o in daily_orders if o.state == OrderState.REJECTED_BY_RISK]

        risk_reasons: Dict[str, int] = {}
        for o in rejected_daily:
            for rid in o.risk_verdict.rule_ids if o.risk_verdict else []:
                risk_reasons[rid] = risk_reasons.get(rid, 0) + 1

        cash = self.broker.get_cash_balance()
        positions = self.broker.get_positions()
        account = self.broker.get_account()
        nav = float(account.get("nav_vnd", 0))
        exposure = sum(float(p.get("market_value_vnd", 0)) for p in positions)
        exposure_pct = exposure / nav if nav > 0 else 0.0

        report: Dict[str, Any] = {
            "asof_date": asof_date,
            "generated_at": utc_now_iso(),
            "strategy": getattr(self.config, "production_strategy", "A3_DP"),
            "config": {
                "broker": self.config.broker,
                "live_trading": self.config.live_trading,
                "dry_run": self.config.dry_run,
                "mode": getattr(self.config, "mode", "paper"),
            },
            "signals": {
                "proposal_count": len(proposals),
                "symbols": [p.signal.symbol for p in proposals],
            },
            "daily_order_counts": {
                "total": len(daily_orders),
                "approved": len([o for o in daily_orders if o.risk_verdict and o.risk_verdict.passed]),
                "rejected": len(rejected_daily),
                "filled": len([o for o in daily_orders if o.state == OrderState.FILLED]),
            },
            "cumulative_order_counts": {
                "total": len(all_orders),
                "filled": len([o for o in all_orders if o.state == OrderState.FILLED]),
            },
            "risk_rejection_reasons": risk_reasons,
            "positions": positions,
            "cash": cash,
            "nav_vnd": nav,
            "exposure_vnd": exposure,
            "exposure_pct_nav": exposure_pct,
            "macro_status": "pending_external_data",
            "reconciliation_issues": recon.has_issues() if recon else None,
        }
        return report

    def save(self, report: Dict[str, Any], asof_date: str) -> Path:
        self.config.reports_dir.mkdir(parents=True, exist_ok=True)
        json_path = self.config.reports_dir / f"daily_report_{asof_date}.json"
        json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        md_path = self.config.reports_dir / f"daily_report_{asof_date}.md"
        md_path.write_text(self._to_markdown(report), encoding="utf-8")
        return md_path

    def _to_markdown(self, r: Dict[str, Any]) -> str:
        d = r.get("daily_order_counts", {})
        c = r.get("cumulative_order_counts", {})
        lines = [
            f"# Daily Trading Report — {r['asof_date']}",
            f"Strategy: {r.get('strategy', 'A3_DP')}",
            "",
            "## Daily order counts",
            f"- Total: {d.get('total', 0)}",
            f"- Approved: {d.get('approved', 0)}",
            f"- Rejected: {d.get('rejected', 0)}",
            f"- Filled: {d.get('filled', 0)}",
            "",
            "## Cumulative order counts",
            f"- Total: {c.get('total', 0)}",
            f"- Filled: {c.get('filled', 0)}",
            "",
            f"Macro: {r.get('macro_status', 'pending_external_data')}",
        ]
        return "\n".join(lines)


def write_dashboard(
    config: LiveTradingConfig,
    asof_date: str,
    intents: pd.DataFrame,
    orders: List[ManagedOrder],
    health: Dict[str, Any],
    kill_switch: Dict[str, Any],
    recon: Dict[str, Any],
) -> None:
    dash = config.dashboard_dir
    dash.mkdir(parents=True, exist_ok=True)
    status = {
        "asof_date": asof_date,
        "strategy": config.production_strategy,
        "mode": config.mode,
        "data_health": health.get("status"),
        "kill_switch": kill_switch.get("status"),
        "reconciliation_block": recon.get("BLOCK_NEW_ORDERS", False),
        "macro_status": "pending_external_data",
    }
    (dash / "live_status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    if not intents.empty:
        intents.to_csv(dash / "order_intents.csv", index=False)
    daily = filter_orders_by_date(orders, asof_date)
    summary_lines = [
        f"# Daily Summary — {asof_date}",
        f"- Strategy: A3_DP",
        f"- Kill switch: {kill_switch.get('status')}",
        f"- Data health: {health.get('status')}",
        f"- Intents: {len(intents)}",
        f"- Daily orders: {len(daily)}",
        f"- Macro: pending external data",
    ]
    (dash / "daily_summary.md").write_text("\n".join(summary_lines), encoding="utf-8")
