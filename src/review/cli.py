"""
CLI for Trade Postmortem Layer: build-input, diagnose, masters, write-lessons, run-monthly.
Idempotent; outputs in data/decision/. Optional --month or --start/--end.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from . import DECISION_DIR, REPO
from . import trade_build_input as build
from . import trade_diagnostic as diag
from . import masters_review as masters
from . import lesson_writer as lessons
from . import open_hygiene as hygiene
from . import meta_perf as meta
from . import open_risk as open_risk_mod
from . import trade_import_excel as importer
from . import current_positions_from_history as positions_derive
from src.quality.validators import (
    validate_trade_review_input,
    validate_trade_diagnostic,
    validate_meta_perf,
    validate_trade_history_full,
    validate_export_month,
    validate_current_positions,
    validate_open_risk,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

TRADE_REVIEW_INPUT_PATH = DECISION_DIR / "trade_review_input.json"


def _default_month() -> str:
    """Latest completed month from manual_inputs or weekly_report."""
    manual = REPO / "data" / "raw" / "manual_inputs.json"
    if manual.exists():
        try:
            d = json.loads(manual.read_text(encoding="utf-8"))
            asof = d.get("asof_date", "")[:10]
            if asof:
                return asof[:7]
        except Exception:
            pass
    from datetime import datetime
    return datetime.now().strftime("%Y-%m")[:7]


def cmd_build_input(args: argparse.Namespace) -> int:
    month = getattr(args, "month", None)
    start = getattr(args, "start", None)
    end = getattr(args, "end", None)
    if not month and not start and not end:
        month = _default_month()
    build.build_input(month=month, start=start, end=end)
    hygiene.write_open_hygiene()
    path = TRADE_REVIEW_INPUT_PATH
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        ok, errs = validate_trade_review_input(payload)
        if not ok:
            logger.warning("Validation: %s", errs)
    return 0


def cmd_diagnose(args: argparse.Namespace) -> int:
    month = getattr(args, "month", None) or _default_month()
    if getattr(args, "start", None) and getattr(args, "end", None):
        month = None
    path = diag.run_diagnostic(month=month)
    if path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        ok, errs = validate_trade_diagnostic(payload)
        if not ok:
            logger.warning("Validation: %s", errs)
    return 0


def cmd_masters(args: argparse.Namespace) -> int:
    month = getattr(args, "month", None) or _default_month()
    masters.run_masters_review(month=month)
    return 0


def cmd_write_lessons(args: argparse.Namespace) -> int:
    month = getattr(args, "month", None) or _default_month()
    lessons.write_lessons(month=month)
    return 0


def cmd_import_full(args: argparse.Namespace) -> int:
    excel_path = getattr(args, "excel", None)
    if not excel_path:
        logger.error("import-full requires --excel <path>")
        return 1
    from pathlib import Path
    try:
        path = importer.run_import_full(Path(excel_path))
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            ok, errs = validate_trade_history_full(payload)
            if not ok:
                logger.warning("Validation: %s", errs)
        return 0
    except Exception as e:
        logger.error("import-full failed: %s", e)
        return 1


def cmd_export_month(args: argparse.Namespace) -> int:
    month = getattr(args, "month", None)
    if not month:
        logger.error("export-month requires --month YYYY-MM")
        return 1
    try:
        path = importer.run_export_month(month)
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            ok, errs = validate_export_month(payload, month)
            if not ok:
                logger.warning("Validation: %s", errs)
        return 0
    except FileNotFoundError as e:
        logger.error("%s", e)
        return 1
    except Exception as e:
        logger.error("export-month failed: %s", e)
        return 1


def cmd_derive_current(args: argparse.Namespace) -> int:
    asof = getattr(args, "asof", None)
    excel = getattr(args, "excel", None)
    excel_path = Path(excel) if excel else None
    if not excel_path and positions_derive.DEFAULT_CURRENT_POSITIONS_EXCEL.exists():
        excel_path = positions_derive.DEFAULT_CURRENT_POSITIONS_EXCEL
    try:
        path = positions_derive.derive(asof=asof, current_positions_excel_path=excel_path)
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            ok, errs = validate_current_positions(payload)
            if not ok:
                logger.warning("Validation: %s", errs)
        return 0
    except FileNotFoundError as e:
        logger.error("%s", e)
        return 1
    except Exception as e:
        logger.error("derive-current failed: %s", e)
        return 1


def cmd_run_monthly(args: argparse.Namespace) -> int:
    month = getattr(args, "month", None)
    start = getattr(args, "start", None)
    end = getattr(args, "end", None)
    if not month:
        month = (start or end)[:7] if (start or end) else _default_month()
    if not importer.FULL_JSON.exists():
        logger.error(
            "Full trade history not imported. Run import-full first.\n"
            "  python -m src.review.cli import-full --excel \"<path to Trade History.xlsx>\""
        )
        return 1
    # 1) Derive current positions (Excel prevails if exists)
    excel_path = positions_derive.DEFAULT_CURRENT_POSITIONS_EXCEL if positions_derive.DEFAULT_CURRENT_POSITIONS_EXCEL.exists() else None
    positions_derive.derive(current_positions_excel_path=excel_path)
    # 2) Export month-filtered closed trades
    importer.run_export_month(month)
    # 3) Build input, then diagnose, masters, lessons, meta-perf
    build.build_input(month=month, start=start, end=end)
    hygiene.write_open_hygiene()
    diag.run_diagnostic(month=month)
    masters.run_masters_review(month=month)
    lessons.write_lessons(month=month)
    # Always compute meta_perf (JSON); --render is for ad-hoc meta-perf command.
    out_json, latest = meta.run_meta_perf(month=month, render=False)
    if out_json.exists():
        payload = json.loads(out_json.read_text(encoding="utf-8"))
        ok, errs = validate_meta_perf(payload)
        if not ok:
            logger.warning("Validation (meta_perf): %s", errs)
    # Open risk dashboard (no --render in run-monthly)
    open_risk_mod.run_open_risk(month=month, render=False)
    logger.info("run-monthly done for %s", month or "ad-hoc")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Trade Postmortem Layer CLI")
    ap.add_argument("--month", default=None, help="YYYY-MM (default: from manual_inputs or current)")
    ap.add_argument("--start", default=None, help="Ad-hoc window start YYYY-MM-DD")
    ap.add_argument("--end", default=None, help="Ad-hoc window end YYYY-MM-DD")
    ap.add_argument("--render", action="store_true", help="Render markdown for meta-perf (meta-perf command only)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_import = sub.add_parser("import-full", help="Import full trade history from Excel -> data/raw/trades/")
    p_import.add_argument("--excel", required=True, help="Path to Trade History.xlsx")
    p_import.set_defaults(_run=cmd_import_full)

    p_export = sub.add_parser("export-month", help="Export month-filtered closed trades -> trade_history_closed.json")
    p_export.add_argument("--month", required=True, help="YYYY-MM")
    p_export.set_defaults(_run=cmd_export_month)

    p_derive = sub.add_parser("derive-current", help="Derive current open positions (from Current positions.xlsx if provided, else from full trade history)")
    p_derive.add_argument("--asof", default=None, help="YYYY-MM-DD (default: today)")
    p_derive.add_argument("--excel", default=None, help="Path to Current positions.xlsx (prevails; default: Downloads/Current positions.xlsx if exists)")
    p_derive.set_defaults(_run=cmd_derive_current)

    p_build = sub.add_parser("build-input", help="Build trade_review_input.json")
    p_build.set_defaults(_run=cmd_build_input)

    p_diag = sub.add_parser("diagnose", help="Run diagnostics -> trade_diagnostic_YYYY-MM.json")
    p_diag.set_defaults(_run=cmd_diagnose)

    p_masters = sub.add_parser("masters", help="Masters review -> trade_masters_review_YYYY-MM.json")
    p_masters.set_defaults(_run=cmd_masters)

    p_lessons = sub.add_parser("write-lessons", help="Write lesson_learned_YYYY-MM.md and latest")
    p_lessons.set_defaults(_run=cmd_write_lessons)

    p_run = sub.add_parser("run-monthly", help="Run all steps (build-input, diagnose, masters, lessons, meta-perf)")
    p_run.add_argument("--month", default=None, help="YYYY-MM")
    p_run.set_defaults(_run=cmd_run_monthly)

    def cmd_meta_perf(args: argparse.Namespace) -> int:
        month = getattr(args, "month", None) or _default_month()
        render = getattr(args, "render", False)
        out_json, _ = meta.run_meta_perf(month=month, render=render)
        if out_json.exists():
            payload = json.loads(out_json.read_text(encoding="utf-8"))
            ok, errs = validate_meta_perf(payload)
            if not ok:
                logger.warning("Validation (meta_perf): %s", errs)
        return 0

    p_meta = sub.add_parser("meta-perf", help="Compute meta performance dashboard (JSON + optional md)")
    p_meta.set_defaults(_run=cmd_meta_perf)

    def cmd_open_risk(args: argparse.Namespace) -> int:
        month = getattr(args, "month", None) or _default_month()
        render = getattr(args, "render", False)
        _, out_latest = open_risk_mod.run_open_risk(month=month, render=render)
        if out_latest.exists():
            payload = json.loads(out_latest.read_text(encoding="utf-8"))
            ok, errs = validate_open_risk(payload)
            if not ok:
                logger.warning("Validation (open_risk): %s", errs)
        return 0

    p_open_risk = sub.add_parser("open-risk", help="Open risk dashboard (position risk × regime × concentration)")
    p_open_risk.add_argument("--month", default=None, help="YYYY-MM (default: from manual_inputs)")
    p_open_risk.add_argument("--render", action="store_true", help="Also write open_risk_*.md")
    p_open_risk.set_defaults(_run=cmd_open_risk)

    args = ap.parse_args()
    return args._run(args)


if __name__ == "__main__":
    sys.exit(main())
