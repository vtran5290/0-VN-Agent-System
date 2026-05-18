#!/usr/bin/env python3
"""CLI for Vietnam auto-trading pipeline (paper-first)."""
from __future__ import annotations

import argparse
import sys
import warnings
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


def _warn_placeholder_propose() -> None:
    warnings.warn(
        "propose uses PlaceholderStrategy (test path only). "
        "Production A3 scan path: live-workflow or build-intents.",
        UserWarning,
        stacklevel=2,
    )


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

    p_propose = sub.add_parser(
        "propose",
        help="[TEST ONLY] PlaceholderStrategy proposals — not production scan path",
    )
    p_propose.add_argument("--asof", required=True, help="As-of date YYYY-MM-DD")

    sub.add_parser(
        "legacy-propose",
        help="Alias for propose (PlaceholderStrategy test path)",
    )

    p_risk = sub.add_parser("risk-review", help="Run risk engine on proposals")
    p_risk.add_argument("--asof", required=True)

    p_exec = sub.add_parser("execute", help="Execute approved orders (paper/dry-run)")
    p_exec.add_argument("--asof", required=True)
    p_exec.add_argument("--broker", default=None, help="paper or dnse")

    p_recon = sub.add_parser("reconcile", help="Reconcile OMS vs broker")
    p_recon.add_argument("--asof", required=True)

    p_report = sub.add_parser("report", help="Generate daily report")
    p_report.add_argument("--asof", required=True)

    p_run = sub.add_parser("run-daily", help="Legacy placeholder daily run")
    p_run.add_argument("--asof", default=None)

    p_lw = sub.add_parser("live-workflow", help="Production: full scan-driven workflow")
    p_lw.add_argument("--mode", required=True, choices=["paper", "dry_run", "live_manual", "live_auto"])
    p_lw.add_argument("--date", required=True)
    p_lw.add_argument("--scan-path", type=Path, default=None, help="Override daily scan CSV")
    p_lw.add_argument("--force", action="store_true", help="Rerun completed daily workflow")
    p_lw.add_argument(
        "--account",
        default=None,
        help="Paper account id (default A3_PROD_PAPER_5B). S3 shadow not allowed here.",
    )

    p_rs = sub.add_parser("resolve-scan", help="Resolve Phase36 scan path for date")
    p_rs.add_argument("--date", required=True)
    p_rs.add_argument("--scan-path", type=Path, default=None)

    pa = sub.add_parser("paper-accounts", help="Paper account management")
    pa_sub = pa.add_subparsers(dest="paper_accounts_cmd", required=True)
    pa_sub.add_parser("list", help="List configured paper accounts")
    pa_init = pa_sub.add_parser("init", help="Initialize paper account ledger")
    pa_init.add_argument("--account", required=True)
    pa_init.add_argument("--reset", action="store_true")
    pa_init.add_argument("--confirm-reset", action="store_true")
    pa_sum = pa_sub.add_parser("summary", help="Account summary")
    pa_sum.add_argument("--account", required=True)
    pa_cmp = pa_sub.add_parser("compare", help="Compare A3 paper accounts")
    pa_cmp.add_argument("--date", required=True)
    pa_run = pa_sub.add_parser("run-all", help="Run all A3 paper workflows for date")
    pa_run.add_argument("--date", required=True)
    pa_run.add_argument("--scan-path", type=Path, default=None)
    pa_run.add_argument("--force", action="store_true")
    pa_run.add_argument("--include-s3-shadow", action="store_true")
    pa_run.add_argument("--allow-sample", action="store_true")
    pa_run.add_argument("--test-mode", action="store_true")
    pa_run.add_argument("--continue-on-error", action="store_true")

    s3 = sub.add_parser("s3-shadow", help="S3 max60 paper-shadow (no OMS)")
    s3_sub = s3.add_subparsers(dest="s3_shadow_cmd", required=True)
    s3_up = s3_sub.add_parser("update", help="Update S3 shadow ledger from scan")
    s3_up.add_argument("--date", required=True)
    s3_up.add_argument("--scan-path", type=Path, default=None)
    s3_up.add_argument("--test-mode", action="store_true")
    s3_sub.add_parser("summary", help="S3 shadow ledger summary")

    p_bh = sub.add_parser("data-health", help="Run data health check")
    p_bh.add_argument("--asof", required=True)
    p_bh.add_argument("--scan-path", type=Path, default=None)

    p_bi = sub.add_parser("build-intents", help="Build order intents from scan (production-safe default)")
    p_bi.add_argument("--asof", required=True)
    p_bi.add_argument("--scan-path", type=Path, default=None)
    p_bi.add_argument("--allow-sample", action="store_true", help="Allow sample scan CSV")
    p_bi.add_argument("--test-mode", action="store_true", help="Relax stale-scan block for fixtures")

    p_mr = sub.add_parser("manual-review", help="Show manual review queue for date")
    p_mr.add_argument("--date", required=True)
    p_mr.add_argument("--account", default=None)

    p_amr = sub.add_parser("apply-manual-review", help="Merge manual review queue into intents")
    p_amr.add_argument("--date", required=True)
    p_amr.add_argument("--account", default=None)

    p_sb = sub.add_parser("snapshot-baseline", help="Snapshot broker positions baseline")
    p_sb.add_argument("--asof", required=True)

    p_is = sub.add_parser(
        "intraday-scan",
        help="Intraday A3/S3 preview scan (manual review only — no OMS routing)",
    )
    p_is.add_argument("--mode", choices=["pre-lunch", "pre-atc", "ad-hoc"], default="ad-hoc")
    p_is.add_argument("--symbols", default="", help="Comma-separated tickers (default: watchlist)")
    p_is.add_argument(
        "--volume-projection",
        default=None,
        choices=["session_time", "historical_curve", "no_projection"],
    )

    args = parser.parse_args(argv)
    from datetime import UTC
    asof = getattr(args, "asof", None) or getattr(args, "date", None) or datetime.now(UTC).strftime("%Y-%m-%d")

    cfg = load_trading_config(data_root_override=args.data_root)
    cfg.ensure_dirs()

    if args.command in ("propose", "legacy-propose"):
        _warn_placeholder_propose()
        props = build_proposals(cfg, asof)
        print(f"Wrote {len(props)} proposals for {asof} [PlaceholderStrategy — not production]")
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
        from src.trading.live.paper_accounts import get_paper_account
        from src.trading.live.workflow import run as run_live
        acct = getattr(args, "account", None)
        if acct:
            pa = get_paper_account(acct)
            if pa.is_s3_shadow:
                print(f"Account {acct} is S3 shadow only. Use: python -m src.trading.cli s3-shadow update")
                return 1
        result = run_live(
            args.mode,
            args.date,
            data_root=args.data_root,
            scan_path=getattr(args, "scan_path", None),
            force=getattr(args, "force", False),
            account_id=acct,
            test_mode=False,
        )
        print(result)
        return 0

    if args.command == "resolve-scan":
        from src.trading.config import load_live_trading_config
        from src.trading.live.scan_resolver import resolve_scan
        lcfg = load_live_trading_config(data_root_override=args.data_root)
        r = resolve_scan(lcfg, args.date, cli_scan_path=getattr(args, "scan_path", None))
        print(
            f"path={r.path} source={r.resolved_scan_source} hash={r.scan_hash} "
            f"sample={r.is_sample} blocked={r.blocked}"
        )
        return 0 if not r.blocked else 1

    if args.command == "paper-accounts":
        from src.trading.live.account_dashboard import account_summary, write_compare_report
        from src.trading.live.paper_accounts import (
            build_live_config_for_account,
            get_paper_account,
            initialize_paper_account,
            list_paper_accounts,
        )
        if args.paper_accounts_cmd == "list":
            for pa in list_paper_accounts():
                print(
                    f"{pa.account_id}\t{pa.type}\tenabled={pa.enabled}\t"
                    f"cash={pa.starting_cash_VND:.0f}\tledger={pa.resolve_ledger_root()}\t"
                    f"strategy={pa.strategy}\tallow_s3={pa.allow_s3}\tallow_pts={pa.allow_pts}"
                )
            return 0
        if args.paper_accounts_cmd == "init":
            paths = initialize_paper_account(
                args.account,
                reset=getattr(args, "reset", False),
                confirm_reset=getattr(args, "confirm_reset", False),
            )
            print(f"Initialized {args.account}: {paths['ledger_root']}")
            return 0
        if args.paper_accounts_cmd == "summary":
            acct = get_paper_account(args.account)
            if acct.is_s3_shadow:
                from src.trading.live.s3_shadow_workflow import s3_shadow_summary
                print(s3_shadow_summary())
                return 0
            cfg, _ = build_live_config_for_account(args.account)
            print(account_summary(cfg, acct))
            return 0
        if args.paper_accounts_cmd == "compare":
            p = write_compare_report(args.date)
            print(f"Compare report: {p}")
            return 0
        if args.paper_accounts_cmd == "run-all":
            from src.trading.live.paper_run_all import run_all_paper_accounts
            result = run_all_paper_accounts(
                args.date,
                scan_path=getattr(args, "scan_path", None),
                force=getattr(args, "force", False),
                include_s3_shadow=getattr(args, "include_s3_shadow", False),
                allow_sample=getattr(args, "allow_sample", False),
                test_mode=getattr(args, "test_mode", False),
                continue_on_error=getattr(args, "continue_on_error", False),
            )
            print(result.get("operator_summary_text") or result)
            return 0 if not result.get("aborted") else 1

    if args.command == "s3-shadow":
        if args.s3_shadow_cmd == "update":
            from src.trading.live.s3_shadow_workflow import update_s3_shadow
            result = update_s3_shadow(
                args.date,
                scan_path=getattr(args, "scan_path", None),
                test_mode=getattr(args, "test_mode", False),
                allow_undated_scan=getattr(args, "test_mode", False),
            )
            print(result)
            return 0 if not result.get("aborted") else 1
        if args.s3_shadow_cmd == "summary":
            from src.trading.live.s3_shadow_workflow import s3_shadow_summary
            print(s3_shadow_summary())
            return 0

    if args.command == "data-health":
        from src.trading.config import load_live_trading_config
        from src.trading.live.data_health import run_data_health, save_data_health
        from src.trading.live.scan_resolver import resolve_scan
        lcfg = load_live_trading_config(data_root_override=args.data_root)
        scan = resolve_scan(lcfg, asof, cli_scan_path=getattr(args, "scan_path", None))
        print(f"Scan: {scan.path} source={scan.resolved_scan_source} sample={scan.is_sample}")
        r = run_data_health(lcfg, asof)
        save_data_health(lcfg, r)
        print(f"Data health: {r.status} block={r.block_order_generation}")
        return 0

    if args.command == "build-intents":
        from src.trading.config import load_live_trading_config
        from src.trading.live.data_health import load_data_health_status, run_data_health, save_data_health
        from src.trading.live.order_intent import build_order_intents, save_order_intents
        from src.trading.live.paper_ledger import PaperLedger
        from src.trading.live.scan_resolver import resolve_scan
        lcfg = load_live_trading_config(data_root_override=args.data_root)
        if getattr(args, "allow_sample", False):
            lcfg.allow_sample_scan = True
        test_mode = bool(getattr(args, "test_mode", False))
        scan = resolve_scan(lcfg, asof, cli_scan_path=getattr(args, "scan_path", None), test_mode=test_mode)
        if scan.blocked:
            print(f"Scan blocked: {scan.errors}")
            return 1
        print(
            f"Scan: {scan.path} source={scan.resolved_scan_source} hash={scan.scan_hash} "
            f"sample={scan.is_sample} stale={scan.is_stale}"
        )
        hs = load_data_health_status(lcfg)
        if hs.get("status") == "UNKNOWN":
            r = run_data_health(lcfg, asof)
            save_data_health(lcfg, r)
            hs = r.to_status_dict()
        intents = build_order_intents(
            lcfg,
            asof,
            hs,
            scan_path=scan.path,
            scan_resolve=scan,
            ledger=PaperLedger(lcfg),
            latest_panel_date=hs.get("latest_panel_date", ""),
            test_mode=test_mode,
        )
        p = save_order_intents(lcfg, asof, intents)
        print(f"Wrote {len(intents)} intents to {p}")
        return 0

    if args.command == "manual-review":
        from src.trading.live.manual_review import pending_summary
        from src.trading.live.paper_accounts import build_live_config_for_account, get_default_account_id
        aid = getattr(args, "account", None) or get_default_account_id()
        lcfg, _ = build_live_config_for_account(aid, data_root_override=args.data_root)
        summary = pending_summary(lcfg, args.date)
        print(summary)
        return 0

    if args.command == "apply-manual-review":
        from src.trading.live.manual_review import apply_queue_to_intents, load_queue
        from src.trading.live.order_intent import load_order_intents, save_order_intents
        from src.trading.live.paper_accounts import build_live_config_for_account, get_default_account_id
        aid = getattr(args, "account", None) or get_default_account_id()
        lcfg, _ = build_live_config_for_account(aid, data_root_override=args.data_root)
        intents = load_order_intents(lcfg, args.date)
        merged = apply_queue_to_intents(lcfg, args.date, intents)
        save_order_intents(lcfg, args.date, merged)
        print(f"Applied manual review queue ({len(load_queue(lcfg, args.date))} rows)")
        return 0

    if args.command == "snapshot-baseline":
        from src.trading.reconciliation.baseline import snapshot_baseline
        broker = get_broker(cfg)
        broker.login()
        path = snapshot_baseline(cfg, broker, asof)
        print(f"Baseline saved: {path}")
        return 0

    if args.command == "intraday-scan":
        from src.trading.intraday.intraday_scan import run_intraday_scan

        syms = [s.strip() for s in (args.symbols or "").split(",") if s.strip()] or None
        df, meta = run_intraday_scan(
            symbols=syms,
            mode=args.mode,
            volume_projection=getattr(args, "volume_projection", None),
        )
        print(
            f"Intraday preview: status={meta.get('status')} rows={len(df)} "
            f"mode={args.mode} capability={meta.get('capability', {}).get('available')}"
        )
        ok_status = meta.get("status") in ("OK", "VNINDEX_ONLY_MACRO")
        return 0 if ok_status or len(df) > 0 else 1

    if args.command == "run-daily":
        _warn_placeholder_propose()
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
        print(f"Daily run complete for {asof} [placeholder path]")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
