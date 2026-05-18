"""Order-intent dry run — human review CSV only. No broker, no OMS execution."""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

# Production scan filter — do not use S3/PTS rows for suggested production action.
A3_PRODUCTION = "A3_PRODUCTION"

# Dates at/after this year are treated as test/fixture placeholders unless --allow-test-sample.
PLACEHOLDER_YEAR_THRESHOLD = 2090

DEFAULT_MAX_STALE_DAYS = 7

OUTPUT_COLUMNS = [
    "date",
    "ticker",
    "current_position_qty",
    "current_position_value",
    "phase36_final_action",
    "suggested_action",
    "suggested_size_value",
    "reason",
    "risk_flag",
    "holding_classification",
    "manual_approval_required",
    "order_sent",
    "notes",
]

HOLDING_A3_MATCHED = "A3_PRODUCTION_MATCHED"
HOLDING_OUTSIDE_A3 = "DISCRETIONARY_OUTSIDE_A3"

# Maps final_action only — no signal recompute, no a3_rank_score.
SUGGESTED_FROM_FINAL_ACTION: dict[str, str] = {
    "TRAIL_EXIT": "REVIEW_EXIT",
    "MAX_HOLD_EXIT": "REVIEW_EXIT",
    "TP1_PARTIAL": "REVIEW_EXIT",
    "NEW_T1": "REVIEW_BUY_T1",
    "NEW_T1_MANUAL_REVIEW_BREADTH": "MANUAL_REVIEW_BREADTH",
    "ADD_T2": "REVIEW_ADD_T2",
    "WAIT_PB": "HOLD_REVIEW",
    "HOLD_T1_ONLY": "HOLD_REVIEW",
    "NO_T2_BREADTH": "HOLD_REVIEW",
    "WATCH_ONLY": "HOLD_REVIEW",
    "SKIP_LIQUIDITY": "NO_ACTION_FAIL_CLOSED",
    "SKIP_VNINDEX_BEAR": "NO_ACTION_FAIL_CLOSED",
}


class OrderIntentDryRunError(Exception):
    """Fail-closed error for dry-run generation."""


def _parse_ymd(s: str) -> datetime:
    return datetime.strptime(s[:10], "%Y-%m-%d")


def _is_placeholder_date(date_str: str) -> bool:
    try:
        return _parse_ymd(date_str).year >= PLACEHOLDER_YEAR_THRESHOLD
    except ValueError:
        return True


def _format_date_notes(requested: str, effective: str, extra: str = "") -> str:
    parts = [f"requested_date={requested}", f"effective_scan_date={effective}"]
    if extra:
        parts.append(extra)
    return "; ".join(parts)


def _load_positions(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise OrderIntentDryRunError(f"Positions file missing: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and "positions" in raw:
        items = raw["positions"]
    elif isinstance(raw, list):
        items = raw
    else:
        raise OrderIntentDryRunError(f"Unrecognized positions JSON shape: {path}")
    if not items:
        raise OrderIntentDryRunError(f"Positions file empty: {path}")
    return items


def _position_qty_value(row: dict[str, Any]) -> tuple[int, float | None]:
    lots = row.get("lots") or row.get("quantity") or 0
    try:
        qty = int(float(lots))
    except (TypeError, ValueError):
        qty = 0
    entry = row.get("entry_price")
    value = None
    if entry is not None and qty:
        try:
            value = float(entry) * qty
        except (TypeError, ValueError):
            value = None
    if row.get("market_value") is not None:
        try:
            value = float(row["market_value"])
        except (TypeError, ValueError):
            pass
    return qty, value


def resolve_effective_scan_date(
    scan_dates: list[str],
    requested: str,
    *,
    allow_test_sample: bool = False,
    max_stale_days: int = DEFAULT_MAX_STALE_DAYS,
) -> tuple[str, str]:
    """
    Pick panel date for scan rows.
    Returns (effective_date, warning_note_fragment).
    """
    requested = requested[:10]
    unique = sorted(set(d.strip()[:10] for d in scan_dates if d and str(d) != "nan"))

    if not unique:
        raise OrderIntentDryRunError("Scan has no usable as_of_date values")

    if allow_test_sample:
        eligible = unique
    else:
        eligible = [d for d in unique if not _is_placeholder_date(d)]
        placeholders = [d for d in unique if _is_placeholder_date(d)]
        if not eligible:
            raise OrderIntentDryRunError(
                f"Scan contains only placeholder/test dates (e.g. {placeholders[:3]}). "
                "Use production scan or pass allow_test_sample for fixtures."
            )

    if requested in eligible:
        return requested, ""

    on_or_before = [d for d in eligible if d <= requested]
    if on_or_before:
        effective = on_or_before[-1]
    else:
        effective = eligible[-1]

    req_dt = _parse_ymd(requested)
    eff_dt = _parse_ymd(effective)
    gap = abs((req_dt - eff_dt).days)
    warn = ""
    if gap > max_stale_days:
        if not allow_test_sample:
            raise OrderIntentDryRunError(
                f"Effective scan date {effective} is {gap} days from requested {requested} "
                f"(max {max_stale_days}). Refresh scan or pass allow_test_sample for fixtures."
            )
        warn = f"STALE_SCAN_GAP_DAYS={gap}"
    elif gap > 0:
        warn = f"SCAN_DATE_FALLBACK gap_days={gap}"

    if _is_placeholder_date(effective) and not allow_test_sample:
        raise OrderIntentDryRunError(
            f"Refusing placeholder effective date {effective}. Use allow_test_sample only for tests."
        )

    return effective, warn


def _load_scan_production_index(
    scan_path: Path,
    asof: str,
    *,
    allow_test_sample: bool = False,
    max_stale_days: int = DEFAULT_MAX_STALE_DAYS,
) -> tuple[pd.DataFrame, str, str, str]:
    """Returns (prod_scan, requested_date, effective_date, date_warn)."""
    if not scan_path.exists():
        raise OrderIntentDryRunError(f"Scan file missing: {scan_path}")
    scan = pd.read_csv(scan_path)
    if scan.empty:
        raise OrderIntentDryRunError(f"Scan file empty: {scan_path}")
    if "as_of_date" not in scan.columns:
        raise OrderIntentDryRunError("Scan missing required column: as_of_date")
    if "symbol" not in scan.columns:
        raise OrderIntentDryRunError("Scan missing required column: symbol")
    if "final_action" not in scan.columns:
        raise OrderIntentDryRunError("Scan missing required column: final_action")

    scan["as_of_date"] = pd.to_datetime(scan["as_of_date"]).dt.strftime("%Y-%m-%d")
    scan["symbol"] = scan["symbol"].astype(str).str.upper().str.strip()

    requested = asof[:10]
    effective, date_warn = resolve_effective_scan_date(
        scan["as_of_date"].tolist(),
        requested,
        allow_test_sample=allow_test_sample,
        max_stale_days=max_stale_days,
    )

    day = scan[scan["as_of_date"] == effective].copy()
    if day.empty:
        raise OrderIntentDryRunError(f"No scan rows for effective date {effective}")

    if "strategy_classification" in day.columns:
        prod = day[day["strategy_classification"].astype(str) == A3_PRODUCTION].copy()
    else:
        prod = day.copy()

    return prod, requested, effective, date_warn


def _map_suggested(final_action: str) -> tuple[str, str, str]:
    fa = (final_action or "").strip()
    if not fa:
        return "NO_ACTION_FAIL_CLOSED", "MISSING_FINAL_ACTION", "final_action empty"
    suggested = SUGGESTED_FROM_FINAL_ACTION.get(fa)
    if suggested is None:
        return "NO_ACTION_FAIL_CLOSED", "UNKNOWN_FINAL_ACTION", f"unmapped final_action={fa}"
    return suggested, "", f"mapped from final_action={fa}"


def generate_order_intent_dry_run(
    asof: str,
    scan_path: Path,
    positions_path: Path,
    output_path: Path,
    *,
    allow_test_sample: bool = False,
    max_stale_days: int = DEFAULT_MAX_STALE_DAYS,
) -> tuple[Path, dict[str, Any]]:
    """
    Build order-intent preview CSV. order_sent is always NO.
    This command does not send broker orders.

    Output `date` column = effective_scan_date (panel date for final_action).
    Notes always include requested_date= and effective_scan_date=.
    """
    positions = _load_positions(positions_path)
    prod_scan, requested, effective, date_warn = _load_scan_production_index(
        scan_path,
        asof,
        allow_test_sample=allow_test_sample,
        max_stale_days=max_stale_days,
    )

    scan_by_symbol: dict[str, pd.Series] = {}
    for _, row in prod_scan.iterrows():
        sym = str(row["symbol"]).upper()
        scan_by_symbol[sym] = row

    out_rows: list[dict[str, Any]] = []
    fail_closed_any = False
    is_test_output = allow_test_sample or _is_placeholder_date(effective)

    for pos in positions:
        ticker = str(pos.get("ticker") or pos.get("symbol") or "").upper().strip()
        if not ticker:
            continue
        qty, value = _position_qty_value(pos)
        scan_row = scan_by_symbol.get(ticker)

        base_notes = _format_date_notes(requested, effective, date_warn)

        if scan_row is None:
            fail_closed_any = True
            notes = "; ".join(
                p
                for p in [
                    base_notes,
                    "No A3_PRODUCTION scan row for ticker",
                    "outside_a3_review=see templates/outside_a3_holding_review_template.md",
                ]
                if p
            )
            out_rows.append({
                "date": effective,
                "ticker": ticker,
                "current_position_qty": qty,
                "current_position_value": value if value is not None else "",
                "phase36_final_action": "",
                "suggested_action": "NO_ACTION_FAIL_CLOSED",
                "suggested_size_value": "",
                "reason": "OUTSIDE_A3_OR_NO_SCAN_MATCH",
                "risk_flag": "OUTSIDE_A3_OR_NO_SCAN_MATCH",
                "holding_classification": HOLDING_OUTSIDE_A3,
                "manual_approval_required": "YES",
                "order_sent": "NO",
                "notes": notes,
            })
            continue

        final_action = str(scan_row.get("final_action", "")).strip()
        if not final_action or (isinstance(final_action, float) and pd.isna(final_action)):
            fail_closed_any = True
            out_rows.append({
                "date": effective,
                "ticker": ticker,
                "current_position_qty": qty,
                "current_position_value": value if value is not None else "",
                "phase36_final_action": "",
                "suggested_action": "NO_ACTION_FAIL_CLOSED",
                "suggested_size_value": "",
                "reason": "MISSING_FINAL_ACTION",
                "risk_flag": "MISSING_FINAL_ACTION",
                "holding_classification": HOLDING_A3_MATCHED,
                "manual_approval_required": "YES",
                "order_sent": "NO",
                "notes": _format_date_notes(requested, effective, "final_action missing"),
            })
            continue

        suggested, risk_flag, reason = _map_suggested(final_action)
        if suggested == "NO_ACTION_FAIL_CLOSED" and risk_flag:
            fail_closed_any = True

        notes = _format_date_notes(requested, effective, reason)
        if date_warn:
            notes = f"{notes}; {date_warn}"

        out_rows.append({
            "date": effective,
            "ticker": ticker,
            "current_position_qty": qty,
            "current_position_value": value if value is not None else "",
            "phase36_final_action": final_action,
            "suggested_action": suggested,
            "suggested_size_value": "",
            "reason": reason,
            "risk_flag": risk_flag or "",
            "holding_classification": HOLDING_A3_MATCHED,
            "manual_approval_required": "YES",
            "order_sent": "NO",
            "notes": notes,
        })

    if not out_rows:
        raise OrderIntentDryRunError("No output rows generated")

    # Refuse production-looking filename with placeholder dates (even in test mode).
    out_name = output_path.name.lower()
    if _is_placeholder_date(effective) and "sample" not in out_name and "test" not in out_name:
        raise OrderIntentDryRunError(
            f"Refusing to write production path {output_path} with placeholder effective date "
            f"{effective}. Use output filename containing 'test' or 'sample'."
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(out_rows, columns=OUTPUT_COLUMNS)
    if (df["order_sent"] != "NO").any():
        raise OrderIntentDryRunError("Invariant violated: order_sent must always be NO")
    if not allow_test_sample and (df["date"].astype(str).str.startswith("2099")).any():
        raise OrderIntentDryRunError("Invariant violated: date column contains placeholder year 2099")

    df.to_csv(output_path, index=False)

    meta = {
        "requested_date": requested,
        "effective_scan_date": effective,
        "date_warn": date_warn,
        "is_test_output": is_test_output,
        "fail_closed_any": fail_closed_any,
        "row_count": len(df),
    }

    if fail_closed_any:
        print(
            f"WARN: order-intent dry run wrote {output_path} with fail-closed rows",
            file=sys.stderr,
        )
    if is_test_output:
        print(
            f"WARN: test/sample scan dates in use (effective={effective})",
            file=sys.stderr,
        )

    validate_order_intent_csv(output_path, allow_test_sample=allow_test_sample)

    return output_path, meta


def validate_order_intent_csv(
    path: Path,
    *,
    allow_test_sample: bool = False,
) -> None:
    """
    Fail-closed validation for operator order-intent CSV artifacts.
    Used by weekly_pareto_operator.ps1 after generation.
    """
    if not path.exists():
        raise OrderIntentDryRunError(f"Order-intent file missing: {path}")
    df = pd.read_csv(path)
    if df.empty:
        raise OrderIntentDryRunError(f"Order-intent file empty: {path}")
    required = {"date", "order_sent"}
    missing_cols = required - set(df.columns)
    if missing_cols:
        raise OrderIntentDryRunError(
            f"Order-intent CSV missing columns: {', '.join(sorted(missing_cols))}"
        )
    if (df["order_sent"].astype(str).str.upper().str.strip() != "NO").any():
        raise OrderIntentDryRunError("Invariant violated: order_sent must always be NO")

    name = path.name.lower()
    is_test_file = "test" in name or "sample" in name

    for idx, raw in enumerate(df["date"].astype(str)):
        d = raw.strip()[:10]
        if not d or d.lower() == "nan":
            raise OrderIntentDryRunError(f"Missing date in row {idx + 2} of {path}")
        if _is_placeholder_date(d):
            if allow_test_sample and is_test_file:
                continue
            raise OrderIntentDryRunError(
                f"Placeholder date '{d}' in row {idx + 2} of {path}. "
                "Delete file and refresh scan, or use a test/sample output filename."
            )

    if "notes" in df.columns and not (allow_test_sample and is_test_file):
        for idx, note in enumerate(df["notes"].astype(str)):
            for year in range(PLACEHOLDER_YEAR_THRESHOLD, 2200):
                token = f"effective_scan_date={year}"
                if token in note:
                    raise OrderIntentDryRunError(
                        f"Placeholder {token} in notes row {idx + 2} of {path}"
                    )


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate order-intent dry run CSV (no broker orders)"
    )
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--scan-path", type=Path, required=True)
    parser.add_argument("--positions-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--allow-test-sample",
        action="store_true",
        help="Allow fixture/placeholder scan dates (tests only)",
    )
    parser.add_argument(
        "--max-stale-days",
        type=int,
        default=DEFAULT_MAX_STALE_DAYS,
        help="Max days between requested and effective scan date",
    )
    args = parser.parse_args(argv)

    try:
        path, meta = generate_order_intent_dry_run(
            args.date,
            args.scan_path,
            args.positions_path,
            args.output,
            allow_test_sample=args.allow_test_sample,
            max_stale_days=args.max_stale_days,
        )
        print(f"Order-intent dry run: {path} (order_sent=NO for all rows)")
        print(
            f"requested_date={meta['requested_date']} "
            f"effective_scan_date={meta['effective_scan_date']}"
        )
        print("This command does not send broker orders")
        df = pd.read_csv(path)
        flagged = (df["risk_flag"].astype(str).str.strip() != "").sum()
        if meta.get("fail_closed_any") or flagged:
            return 2
        return 0
    except OrderIntentDryRunError as e:
        print(f"FAIL-CLOSED: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
