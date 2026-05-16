"""Live workflow orchestration."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from src.trading.config import load_live_trading_config
from src.trading.live.data_health import load_data_health_status, run_data_health, save_data_health
from src.trading.live.order_intent import (
    build_order_intents,
    intents_to_proposals,
    load_order_intents,
    save_order_intents,
)
from src.trading.live.paper_ledger import PaperLedger
from src.trading.models import proposals_path, save_proposals
from src.trading.monitoring.daily_report import DailyReportBuilder, filter_orders_by_date, write_dashboard
from src.trading.monitoring.monitor import run_monitoring
from src.trading.oms.order_manager import OrderManager, get_broker, portfolio_from_broker
from src.trading.reconciliation.reconciler import Reconciler


def run(mode: str, asof_date: str, data_root: Path | None = None) -> Dict[str, Any]:
    config = load_live_trading_config(data_root_override=data_root)
    config.mode = mode
    config.ensure_dirs()

    if mode == "live_auto" and not config.live_auto_allowed():
        raise RuntimeError("live_auto disabled. Set enable_live_auto: true in a future approved phase.")

    # 1–2 data health
    health = run_data_health(config, asof_date)
    save_data_health(config, health)
    health_status = health.to_status_dict()

    broker = get_broker(config)
    broker.login()
    om = OrderManager(config, broker=broker)
    ledger = PaperLedger(config)

    # 3–5 order intents from scan
    intents = build_order_intents(
        config, asof_date, health_status, ledger=ledger, latest_panel_date=health.latest_panel_date
    )
    save_order_intents(config, asof_date, intents)

    # 6 batch risk
    portfolio = portfolio_from_broker(broker, asof_date)
    proposals = intents_to_proposals(
        intents, asof_date, portfolio.nav_vnd, latest_panel_date=health.latest_panel_date
    )
    save_proposals(proposals_path(config.data_root, asof_date), proposals)

    recon_pre = {"BLOCK_NEW_ORDERS": False}
    extra = {"data_health": health_status, "kill_switch": {"status": "CLEAR"}, "reconciliation": recon_pre}
    om.risk_review_proposals(asof_date, extra=extra, live_config=config)

    # 7 kill switch
    ks = run_monitoring(config, asof_date, health_status, recon_pre)

    # 8–10 execute per mode
    extra["kill_switch"] = ks
    if mode == "paper":
        config.live_trading = True
        config.dry_run = True
    elif mode == "dry_run":
        config.dry_run = True
        config.live_trading = False
    elif mode == "live_manual":
        config.dry_run = True
        config.live_trading = False

    om.execute_approved(asof_date, live_config=config, extra=extra)

    # 11 reconcile
    recon = Reconciler(config, broker, om).run(asof_date)
    Reconciler(config, broker, om).save_report(recon)
    recon_status_path = Reconciler(config, broker, om).save_live_status(recon)

    # 12–14 dashboard
    report = DailyReportBuilder(config, broker, om).build(asof_date, recon)
    DailyReportBuilder(config, broker, om).save(report, asof_date)
    write_dashboard(config, asof_date, intents, om.load_all_orders(), health_status, ks, recon.to_dict())

    return {
        "mode": mode,
        "asof_date": asof_date,
        "data_health": health.status,
        "intents_count": len(intents),
        "kill_switch": ks.get("status"),
        "reconciliation_issues": recon.has_issues(),
    }
