from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import REPO, ScanConfig
from .pipeline import run_institutional_accumulation_scan
from .validation import confirm_no_lookahead, run_spot_checks


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Institutional Accumulation Scan (research ranking; not execution)."
    )
    ap.add_argument("--as-of", dest="as_of", help="Scan date YYYY-MM-DD (default: latest VNINDEX bar)")
    ap.add_argument("--smart-money-month", help="YYYY-MM for monthly context file")
    ap.add_argument("--watchlist", type=Path, help="Limit universe to watchlist file")
    ap.add_argument("--symbols", nargs="*", help="Explicit symbol list")
    ap.add_argument("--min-adv20", type=float, default=2_000_000_000.0)
    ap.add_argument("--min-adv50", type=float, default=1_500_000_000.0)
    ap.add_argument("--min-history", type=int, default=120)
    ap.add_argument("--output-dir", type=Path, default=None)
    ap.add_argument("--validate-only", action="store_true", help="Run spot-check validation on existing/latest scan")
    ap.add_argument(
        "--sync-weekly-html",
        action="store_true",
        help="Refresh weekly brief HTML from existing institutional_accumulation_weekly_brief_{date}.md",
    )
    ap.add_argument(
        "--regenerate-weekly-brief",
        action="store_true",
        help="Overwrite weekly brief MD skeleton then sync HTML (scan CSV must exist)",
    )
    args = ap.parse_args(argv)

    cfg = ScanConfig(
        scan_date=args.as_of,
        smart_money_month=args.smart_money_month,
        watchlist_path=args.watchlist,
        symbols=[s.upper() for s in args.symbols] if args.symbols else None,
        min_adv20_vnd=args.min_adv20,
        min_adv50_vnd=args.min_adv50,
        min_history_days=args.min_history,
    )
    if args.output_dir:
        cfg.output_dir = args.output_dir

    if args.validate_only:
        return _validate_only(cfg)

    if args.sync_weekly_html or args.regenerate_weekly_brief:
        return _sync_weekly_html_only(cfg, regenerate_md=args.regenerate_weekly_brief)

    result = run_institutional_accumulation_scan(cfg)
    summary = {
        "scan_date": result.get("scan_date"),
        "rows": result.get("rows"),
        "outputs": result.get("outputs"),
    }
    print(json.dumps(summary, indent=2))
    return 0


def _sync_weekly_html_only(cfg: ScanConfig, *, regenerate_md: bool) -> int:
    import pandas as pd

    from .weekly_brief import sync_weekly_brief_html

    latest = cfg.output_dir / "institutional_accumulation_latest.csv"
    dated = None
    if cfg.scan_date:
        dated = cfg.output_dir / f"institutional_accumulation_{cfg.scan_date}.csv"
    csv_path = dated if dated and dated.is_file() else latest
    if not csv_path.is_file():
        print(f"No scan CSV at {csv_path}", file=sys.stderr)
        return 1
    df = pd.read_csv(csv_path)
    scan_date = str(df["scan_date"].iloc[0]) if "scan_date" in df.columns else (cfg.scan_date or "")
    if not scan_date:
        print("Cannot determine scan_date", file=sys.stderr)
        return 1
    json_path = cfg.output_dir / f"institutional_accumulation_{scan_date}.json"
    scan_json: dict = {}
    if json_path.is_file():
        scan_json = json.loads(json_path.read_text(encoding="utf-8"))
    op_json = cfg.output_dir / f"institutional_accumulation_operator_summary_{scan_date}.json"
    op_payload: dict = {}
    if op_json.is_file():
        op_payload = json.loads(op_json.read_text(encoding="utf-8"))
    elif regenerate_md:
        print(f"Missing operator summary JSON: {op_json}; run full scan first.", file=sys.stderr)
        return 1
    paths = sync_weekly_brief_html(
        cfg.output_dir,
        scan_date,
        regenerate_md=regenerate_md,
        op_payload=op_payload or None,
        df=df if regenerate_md else None,
        scan_json=scan_json if regenerate_md else None,
    )
    print(json.dumps({"scan_date": scan_date, "outputs": paths}, indent=2))
    return 0


def _validate_only(cfg: ScanConfig) -> int:
    import pandas as pd

    latest = cfg.output_dir / "institutional_accumulation_latest.csv"
    if not latest.is_file():
        print(f"No latest scan at {latest}; run scan first.", file=sys.stderr)
        return 1
    df = pd.read_csv(latest)
    scan_date = str(df["scan_date"].iloc[0]) if "scan_date" in df.columns else cfg.scan_date
    print("=== Spot checks ===")
    print(json.dumps(run_spot_checks(df, scan_date or ""), indent=2))
    for sym in ["MBB", "VIC"]:
        ok = confirm_no_lookahead(sym, cfg.stocks_dir, scan_date or "")
        print(f"no_lookahead {sym}: {ok}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
