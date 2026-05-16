#!/usr/bin/env python3
"""CLI for Vietnam auto-trading pipeline (paper-first)."""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))


def _load_dotenv() -> None:
    env_path = REPO / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k, v = k.strip(), v.strip()
        if k and k not in __import__("os").environ:
            __import__("os").environ[k] = v


def main(argv: list[str] | None = None) -> int:
    _load_dotenv()
    from src.trading.config import load_trading_config
    from src.trading.monitoring.alerts import MockAlertHook
    from src.trading.monitoring.daily_report import DailyReportBuilder
    from src.trading.oms.order_manager import OrderManager, get_broker
    from src.trading.pipeline import build_proposals
    from src.trading.reconciliation.reconciler import Reconciler

    parser = argparse.ArgumentParser(description="VN auto-trading pipeline")
    parser.add_argument(
        "--data-root",
        type=Path,
        default=None,
        help="Override data/trading root",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_propose = sub.add_parser("propose", help="Generate order proposals")
    p_propose.add_argument("--asof", required=True, help="As-of date YYYY-MM-DD")

    p_risk = sub.add_parser("risk-review", help="Run risk engine on proposals")
    p_risk.add_argument("--asof", required=True)

    p_exec = sub.add_parser("execute", help="Execute approved orders (paper/dry-run)")
    p_exec.add_argument("--asof", required=True)
    p_exec.add_argument("--broker", default=None, help="paper or dnse")

    p_recon = sub.add_parser("reconcile", help="Reconcile OMS vs broker")
    p_recon.add_argument("--asof", required=True)

    p_report = sub.add_parser("report", help="Generate daily report")
    p_report.add_argument("--asof", required=True)

    p_run = sub.add_parser("run-daily", help="propose -> risk -> execute(dry) -> reconcile -> report")
    p_run.add_argument("--asof", default=None)

    p_lw = sub.add_parser("live-workflow", help="Full live readiness workflow")
    p_lw.add_argument("--mode", required=True, choices=["paper", "dry_run", "live_manual", "live_auto"])
    p_lw.add_argument("--date", required=True)

    p_bh = sub.add_parser("data-health", help="Run data health check")
    p_bh.add_argument("--asof", required=True)

    p_bi = sub.add_parser("build-intents", help="Build order intents from scan")
    p_bi.add_argument("--asof", required=True)

    p_sb = sub.add_parser("snapshot-baseline", help="Snapshot broker positions baseline")
    p_sb.add_argument("--asof", required=True)

    args = parser.parse_args(argv)
    from src.trading.util.timeutil import utc_now_iso
    from datetime import datetime, UTC
    asof = getattr(args, "asof", None) or getattr(args, "date", None) or datetime.now(UTC).strftime("%Y-%m-%d")

    cfg = load_trading_config(data_root_override=args.data_root)
    cfg.ensure_dirs()

    if args.command == "propose":
        props = build_proposals(cfg, asof)
        print(f"Wrote {len(props)} proposals for {asof}")
        return 0

    om = OrderManager(cfg)
    alerts = MockAlertHook(log_path=cfg.data_root / "alerts.jsonl")

    if args.command == "risk-review":
        orders = om.risk_review_proposals(asof)
        approved = sum(1 for o in orders if o.risk_verdict and o.risk_verdict.passed)
        rejected = len(orders) - approved
        print(f"Risk review {asof}: {approved} approved, {rejected} rejected")
        return 0

    if args.command == "execute":
        if args.broker:
            import os
            os.environ["BROKER"] = args.broker
            cfg = load_trading_config(data_root_override=args.data_root)
            om = OrderManager(cfg)
        executed = om.execute_approved(asof)
        print(f"Execute {asof}: processed {len(executed)} orders (dry_run={cfg.dry_run})")
        return 0

    if args.command == "reconcile":
        broker = get_broker(cfg)
        broker.login()
        recon = Reconciler(cfg, broker, om)
        report = recon.run(asof)
        path = recon.save_report(report)
        if report.has_issues():
            alerts.send("warning", f"Reconciliation issues on {asof}", report.to_dict())
        print(f"Reconciliation saved: {path} (issues={report.has_issues()})")
        return 0

    if args.command == "report":
        broker = get_broker(cfg)
        broker.login()
        recon_report = None
        recon_path = cfg.reconciliation_dir / f"recon_{asof}.json"
        if recon_path.exists():
            import json
            from src.trading.reconciliation.reconciler import ReconciliationReport
            recon_report = ReconciliationReport(**json.loads(recon_path.read_text(encoding="utf-8")))
        builder = DailyReportBuilder(cfg, broker, om)
        report = builder.build(asof, recon_report)
        path = builder.save(report, asof)
        print(f"Report saved: {path}")
        return 0

    if args.command == "live-workflow":
        from src.trading.live.workflow import run as run_live
        result = run_live(args.mode, args.date, data_root=args.data_root)
        print(result)
        return 0

    if args.command == "data-health":
        from src.trading.config import load_live_trading_config
        from src.trading.live.data_health import run_data_health, save_data_health
        lcfg = load_live_trading_config(data_root_override=args.data_root)
        r = run_data_health(lcfg, asof)
        save_data_health(lcfg, r)
        print(f"Data health: {r.status} block={r.block_order_generation}")
        return 0

    if args.command == "build-intents":
        from src.trading.config import load_live_trading_config
        from src.trading.live.data_health import load_data_health_status, run_data_health, save_data_health
        from src.trading.live.order_intent import build_order_intents, save_order_intents
        from src.trading.live.paper_ledger import PaperLedger
        lcfg = load_live_trading_config(data_root_override=args.data_root)
        hs = load_data_health_status(lcfg)
        if hs.get("status") == "UNKNOWN":
            r = run_data_health(lcfg, asof)
            save_data_health(lcfg, r)
            hs = r.to_status_dict()
        intents = build_order_intents(lcfg, asof, hs, ledger=PaperLedger(lcfg), latest_panel_date=hs.get("latest_panel_date", ""))
        p = save_order_intents(lcfg, asof, intents)
        print(f"Wrote {len(intents)} intents to {p}")
        return 0

    if args.command == "snapshot-baseline":
        from src.trading.reconciliation.baseline import snapshot_baseline
        broker = get_broker(cfg)
        broker.login()
        path = snapshot_baseline(cfg, broker, asof)
        print(f"Baseline saved: {path}")
        return 0

    if args.command == "run-daily":
        build_proposals(cfg, asof)
        om.risk_review_proposals(asof)
        om.execute_approved(asof)
        broker = get_broker(cfg)
        broker.login()
        recon = Reconciler(cfg, broker, om)
        report = recon.run(asof)
        recon.save_report(report)
        builder = DailyReportBuilder(cfg, broker, om)
        r = builder.build(asof, report)
        builder.save(r, asof)
        print(f"Daily run complete for {asof}")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
