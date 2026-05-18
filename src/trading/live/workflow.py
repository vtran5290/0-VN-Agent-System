"""Live workflow orchestration."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Optional

from src.trading.config import load_live_trading_config
from src.trading.live.account_dashboard import write_account_abort_status, write_account_dashboard
from src.trading.live.data_health import run_data_health, save_data_health
from src.trading.live.manual_review import apply_queue_to_intents, sync_queue_from_intents
from src.trading.live.order_intent import build_order_intents, intents_to_proposals, save_order_intents
from src.trading.live.paper_accounts import build_live_config_for_account, get_default_account_id
from src.trading.live.paper_ledger import PaperLedger
from src.trading.live.recon_status import load_reconciliation_status, reconciliation_extra_for_mode
from src.trading.live.run_lock import DailyRunLock, RunLockError
from src.trading.live.scan_resolver import resolve_scan
from src.trading.models import proposals_path, save_proposals
from src.trading.monitoring.daily_report import DailyReportBuilder, write_dashboard
from src.trading.monitoring.monitor import run_monitoring
from src.trading.oms.order_manager import OrderManager, get_broker, portfolio_from_broker
from src.trading.reconciliation.reconciler import Reconciler


def _config_hash(config: Any) -> str:
    raw = json.dumps(
        {
            "mode": config.mode,
            "max_slots": config.max_slots,
            "max_daily_orders": config.max_daily_orders,
            "production_strategy": config.production_strategy,
            "account_id": getattr(config, "account_id", ""),
        },
        sort_keys=True,
    )
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def _abort_payload(
    mode: str,
    asof_date: str,
    account_id: str,
    error: Any,
    *,
    scan: Optional[Dict[str, Any]] = None,
    run_lock_details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "mode": mode,
        "asof_date": asof_date,
        "account_id": account_id,
        "error": error,
        "aborted": True,
    }
    if scan is not None:
        out["scan"] = scan
    if run_lock_details:
        out["run_lock_details"] = run_lock_details
    return out


def run(
    mode: str,
    asof_date: str,
    data_root: Path | None = None,
    scan_path: Optional[Path] = None,
    force: bool = False,
    *,
    account_id: Optional[str] = None,
    test_mode: bool = False,
    ledger_root_override: Optional[Path] = None,
    use_legacy_paths: bool = False,
) -> Dict[str, Any]:
    paper_acct = None
    if use_legacy_paths:
        config = load_live_trading_config(data_root_override=data_root)
    else:
        aid = account_id or get_default_account_id()
        config, paper_acct = build_live_config_for_account(
            aid,
            data_root_override=data_root,
            ledger_root_override=ledger_root_override,
        )
    config.mode = mode
    config.broker = "paper" if mode == "paper" else config.broker
    if test_mode:
        config.allow_sample_scan = True
    config.ensure_dirs()
    for d in (
        config.run_locks_dir,
        config.run_manifests_dir,
        config.orders_dir,
        config.order_proposals_dir,
        config.dashboard_dir,
    ):
        d.mkdir(parents=True, exist_ok=True)

    if mode == "live_auto" and not config.live_auto_allowed():
        raise RuntimeError("live_auto disabled. Set enable_live_auto: true in a future approved phase.")

    run_lock = DailyRunLock(config)
    manifest = None
    aid = getattr(config, "account_id", "") or ""
    try:
        manifest = run_lock.acquire(asof_date, mode, force=force, account_id=aid)
    except RunLockError as e:
        if paper_acct is not None:
            write_account_abort_status(
                config,
                paper_acct,
                asof_date,
                "run_lock_conflict",
                str(e),
                manifest_info=getattr(e, "details", None),
            )
        return _abort_payload(
            mode,
            asof_date,
            aid,
            str(e),
            run_lock_details=getattr(e, "details", None),
        )

    try:
        allow_sample_flag = test_mode or bool(config.allow_sample_scan)
        scan_resolve = resolve_scan(
            config,
            asof_date,
            cli_scan_path=scan_path,
            test_mode=test_mode,
            allow_sample=True if allow_sample_flag else None,
        )
        if scan_resolve.blocked and not test_mode:
            run_lock.fail(manifest, "; ".join(scan_resolve.errors))
            abort_reason = "stale_scan" if scan_resolve.is_stale else "scan_blocked"
            if paper_acct is not None:
                write_account_abort_status(
                    config,
                    paper_acct,
                    asof_date,
                    abort_reason,
                    "; ".join(scan_resolve.errors) or "; ".join(scan_resolve.warnings),
                    scan_meta=scan_resolve.metadata,
                )
            return _abort_payload(
                mode,
                asof_date,
                aid,
                scan_resolve.errors,
                scan=scan_resolve.metadata,
            )

        health = run_data_health(config, asof_date)
        if scan_resolve.block_order_generation:
            health.block_order_generation = True
            health.status = "WARN" if health.status == "PASS" else health.status
        save_data_health(config, health)
        health_status = health.to_status_dict()
        health_status["scan_resolve"] = scan_resolve.metadata
        health_status["is_stale"] = scan_resolve.is_stale

        persisted_recon = load_reconciliation_status(config)
        recon_pre = reconciliation_extra_for_mode(config, mode, persisted_recon)

        broker = get_broker(config)
        broker.login()
        om = OrderManager(config, broker=broker)
        ledger = PaperLedger(config)

        intents = build_order_intents(
            config,
            asof_date,
            health_status,
            scan_path=scan_resolve.path,
            scan_resolve=scan_resolve,
            ledger=ledger,
            latest_panel_date=health.latest_panel_date,
            test_mode=test_mode,
        )
        save_order_intents(config, asof_date, intents)
        sync_queue_from_intents(config, asof_date, intents, scan_hash=scan_resolve.scan_hash or "")
        intents = apply_queue_to_intents(config, asof_date, intents)
        save_order_intents(config, asof_date, intents)

        portfolio = portfolio_from_broker(broker, asof_date)
        proposals = intents_to_proposals(
            intents,
            asof_date,
            portfolio.nav_vnd,
            latest_panel_date=health.latest_panel_date,
            config=config,
        )
        prop_root = config.account_root if config.account_root else config.data_root
        save_proposals(proposals_path(prop_root, asof_date), proposals)

        extra: Dict[str, Any] = {
            "data_health": health_status,
            "kill_switch": {"status": "CLEAR"},
            "reconciliation": recon_pre,
        }
        om.risk_review_proposals(asof_date, extra=extra, live_config=config)

        ks = run_monitoring(config, asof_date, health_status, recon_pre)
        extra["kill_switch"] = ks

        if mode == "paper":
            config.live_trading = True
            config.dry_run = False
            config.broker = "paper"
        elif mode == "dry_run":
            config.dry_run = True
            config.live_trading = False
        elif mode in ("live_manual", "live_auto"):
            config.dry_run = True
            config.live_trading = False

        executed = om.execute_approved(
            asof_date, live_config=config, extra=extra, paper_ledger=ledger if mode == "paper" else None
        )
        paper_fills = extra.get("_paper_fills", sum(1 for o in executed if o.state.value == "FILLED"))

        reconciler = Reconciler(config, broker, om)
        recon = reconciler.run(asof_date)
        reconciler.save_report(recon)
        reconciler.save_live_status(recon)

        report = DailyReportBuilder(config, broker, om).build(asof_date, recon)
        DailyReportBuilder(config, broker, om).save(report, asof_date)
        if mode == "paper":
            ledger.export_dashboard()
            if paper_acct is not None:
                write_account_dashboard(
                    config,
                    paper_acct,
                    asof_date,
                    intents=intents,
                    orders=executed,
                    health_status=health_status,
                    kill_switch=ks,
                    scan_meta=scan_resolve.metadata,
                )
        write_dashboard(config, asof_date, intents, om.load_all_orders(), health_status, ks, recon.to_dict())

        result = {
            "mode": mode,
            "asof_date": asof_date,
            "account_id": aid,
            "ledger_root": str(config.account_root or config.live_dir),
            "data_health": health.status,
            "intents_count": len(intents),
            "proposal_count": len(proposals),
            "paper_fills": paper_fills,
            "kill_switch": ks.get("status"),
            "reconciliation_issues": recon.has_issues(),
            "scan": scan_resolve.metadata,
            "recon_pre_block": recon_pre.get("BLOCK_NEW_ORDERS"),
        }

        run_lock.complete(
            manifest,
            scan_file=str(scan_resolve.path),
            scan_hash=scan_resolve.scan_hash,
            config_hash=_config_hash(config),
            data_health_status=health.status,
            intent_count=len(intents),
            proposal_count=len(proposals),
            orders_submitted=sum(1 for o in executed if o.state.value in ("ORDER_SUBMITTED", "FILLED")),
            paper_fills=paper_fills,
            kill_switch_status=ks.get("status", ""),
            reconciliation_status="BLOCK" if recon.has_issues() else "OK",
        )
        return result
    except Exception as e:
        if manifest:
            run_lock.fail(manifest, str(e))
        if paper_acct is not None:
            write_account_abort_status(
                config,
                paper_acct,
                asof_date,
                "workflow_aborted",
                str(e),
            )
        raise
