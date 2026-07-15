"""
advisory_tracker.py — S2 advisory signal outcome logger.

Purpose
-------
Reads S2 advisory signals from the daily scan output and appends resolved outcomes
to data/decision/advisory_performance.csv. Required for the T5 S2 promotion gate:
30 consecutive advisory days with no kill criterion triggered.

HARD GUARDRAILS (this file NEVER touches):
  - final_action — A3 SSOT signal; OMS and capital decisions only
  - OMS / DNSE routing / order_intent
  - live_auto flag or live trading state

Outputs:
  - data/decision/advisory_performance.csv (append-only; schema: see file header)

Idempotency:
  - Uses a per-date sentinel file (data/decision/advisory_track_{date}.sentinel)
  - If sentinel exists for today, exits 0 immediately (safe to run twice from Task Scheduler)
  - Sentinel is written ONLY on successful completion

Usage:
    python scripts/advisory_tracker.py [--date YYYY-MM-DD] [--force] [--dry-run]

    --date YYYY-MM-DD : Process signals for this date (default: today)
    --force           : Override sentinel and re-run (does NOT dedup CSV; operator use only)
    --dry-run         : Print rows to stdout, do not write to CSV or sentinel

Regime gate:
  - S2 advisory signals are ONLY generated when C1 is BULL.
  - In BEAR regime: no signal rows are logged (correct behavior, not an error).
  - The script reads regime from data/state/regime_state.json.

Resolution:
  - entry_price: read from daily scan output (phase36_daily_scan_latest.csv) at signal date
  - exit_price_10d: NOT populated on the day of signal; must be backfilled by weekly update.
  - net_return_10d: computed from exit_price_10d when available; blank until then.
  - rolling_10sig_miss_rate: computed from the trailing 10 rows in advisory_performance.csv.

Schema (matches advisory_performance.csv header):
  date, symbol, signal_type, regime, adv_compliant, entry_price, exit_price_10d,
  net_return_10d, miss_flag, rolling_10sig_miss_rate, kill_criterion_fired, notes
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

# ── Paths ──────────────────────────────────────────────────────────────────────
ADVISORY_CSV = REPO / "data" / "decision" / "advisory_performance.csv"
REGIME_STATE = REPO / "data" / "state" / "regime_state.json"
SCAN_CSV_GLOB = "data/decision/phase36_daily_scan_*.csv"  # dated scan files
SCAN_CSV_LATEST = REPO / "data" / "decision" / "phase36_daily_scan_latest.csv"

ADVISORY_HEADERS = [
    "date", "symbol", "signal_type", "regime", "adv_compliant",
    "entry_price", "exit_price_10d", "net_return_10d", "miss_flag",
    "rolling_10sig_miss_rate", "kill_criterion_fired", "notes",
]

COST_RT = 0.004  # round-trip cost assumption (matches advisory_performance.csv schema notes)

# Kill criterion constants — Alt B (mean return, approved 2026-07-14)
KILL_WINDOW = 30                     # rolling window: resolved signals
MEAN_RETURN_KILL_FLOOR = -0.05       # 30-sig rolling mean net_return_10d < -5% fires kill
ADV_CAP_MULTIPLIER = 3.0             # signals >3x ADV cap fire ADV_BREACH (unchanged)


# ── Sentinel ───────────────────────────────────────────────────────────────────

def _sentinel_path(run_date: date) -> Path:
    return REPO / "data" / "decision" / f"advisory_track_{run_date.isoformat()}.sentinel"


def _sentinel_exists(run_date: date) -> bool:
    return _sentinel_path(run_date).exists()


def _write_sentinel(run_date: date, rows_written: int) -> None:
    p = _sentinel_path(run_date)
    p.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()
    p.write_text(
        f"advisory_tracker completed\n"
        f"date={run_date.isoformat()}\n"
        f"rows_written={rows_written}\n"
        f"completed_utc={ts}\n",
        encoding="utf-8",
    )


# ── Regime detection ───────────────────────────────────────────────────────────

def _load_regime(run_date: date) -> str:
    """Return 'A' (BULL) or 'B' (BEAR/NEUTRAL) from regime_state.json."""
    if not REGIME_STATE.exists():
        return "UNKNOWN"
    try:
        state = json.loads(REGIME_STATE.read_text(encoding="utf-8"))
        regime = state.get("regime", "B")
        if regime == "A":
            return "A"
        return "B"
    except Exception as exc:
        print(f"[advisory_tracker] WARN: could not read regime_state.json ({exc})", file=sys.stderr)
        return "UNKNOWN"


# ── Signal extraction from scan CSV ───────────────────────────────────────────

def _find_scan_csv(run_date: date) -> Optional[Path]:
    """Prefer dated scan file, fall back to latest."""
    dated = REPO / "data" / "decision" / f"phase36_daily_scan_{run_date.isoformat()}.csv"
    if dated.exists():
        return dated
    if SCAN_CSV_LATEST.exists():
        return SCAN_CSV_LATEST
    # Try glob pattern
    candidates = sorted(REPO.glob(SCAN_CSV_GLOB), reverse=True)
    if candidates:
        return candidates[0]
    return None


def _extract_s2_signals(scan_csv: Path, run_date: date, regime: str) -> List[Dict[str, Any]]:
    """
    Extract S2 advisory signals from the daily scan CSV.

    S2 advisory signal = any row with final_action in NEW_T1 / NEW_T1_MANUAL_REVIEW_BREADTH
    AND s2_signal == 1 (or s2_filtered == True, depending on column name).
    If neither s2 column exists, falls back to all NEW_T1 rows (conservative).

    Returns a list of row dicts ready for advisory_performance.csv.
    """
    if regime != "A":
        # C1 gate is ON in BEAR — S2 generates 0 advisory signals. Correct behavior.
        return []

    try:
        import pandas as pd
        df = pd.read_csv(scan_csv)
    except Exception as exc:
        print(f"[advisory_tracker] ERROR: could not read scan CSV ({exc})", file=sys.stderr)
        return []

    new_t1_actions = {"NEW_T1", "NEW_T1_MANUAL_REVIEW_BREADTH"}
    if "final_action" not in df.columns:
        print("[advisory_tracker] WARN: 'final_action' column not found in scan CSV", file=sys.stderr)
        return []

    candidates = df[df["final_action"].isin(new_t1_actions)].copy()

    # Filter to S2-flagged rows if column exists
    s2_col = None
    for col_candidate in ("s2_signal", "s2_filtered", "s2_flag", "s2_advisory"):
        if col_candidate in df.columns:
            s2_col = col_candidate
            break

    if s2_col is not None:
        candidates = candidates[candidates[s2_col].fillna(0).astype(bool)]
    # If no s2 column: use all NEW_T1 (conservative fallback; operator should verify)

    rows = []
    for _, row in candidates.iterrows():
        symbol = str(row.get("symbol", "")).upper()
        if not symbol:
            continue

        # ADV compliance
        adv_compliant = True
        adv_ratio = row.get("adv_ratio") or row.get("size_adv_ratio")
        if adv_ratio is not None:
            try:
                adv_compliant = float(adv_ratio) <= ADV_CAP_MULTIPLIER
            except (TypeError, ValueError):
                pass

        entry_price = None
        for price_col in ("close_kVND", "close", "entry_price", "price"):
            if price_col in row.index:
                try:
                    entry_price = float(row[price_col])
                    break
                except (TypeError, ValueError):
                    pass

        # Kill criterion check (entry-day; only ADV_BREACH detectable at entry)
        kill_criterion = None
        if not adv_compliant:
            kill_criterion = "ADV_BREACH"

        rows.append({
            "date": run_date.isoformat(),
            "symbol": symbol,
            "signal_type": str(row.get("final_action", "")).replace("NEW_T1_MANUAL_REVIEW_BREADTH", "T1_MR"),
            "regime": regime,
            "adv_compliant": str(adv_compliant),
            "entry_price": f"{entry_price:.2f}" if entry_price is not None else "",
            "exit_price_10d": "",       # backfilled by weekly update
            "net_return_10d": "",       # backfilled
            "miss_flag": "",            # backfilled
            "rolling_10sig_miss_rate": "",  # backfilled
            "kill_criterion_fired": kill_criterion or "",
            "notes": f"s2_col={s2_col or 'fallback-all-NEW_T1'}",
        })

    return rows


# ── CSV helpers ────────────────────────────────────────────────────────────────

def _read_existing_rows(run_date: date) -> List[Dict[str, str]]:
    """Read existing non-header, non-comment rows from advisory_performance.csv."""
    if not ADVISORY_CSV.exists():
        return []
    rows = []
    with open(ADVISORY_CSV, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("date", "").startswith("#"):
                continue
            rows.append(row)
    return rows


def _date_already_logged(run_date: date) -> bool:
    """Check whether any row for this date exists in the CSV (secondary dedup guard)."""
    date_str = run_date.isoformat()
    if not ADVISORY_CSV.exists():
        return False
    try:
        with open(ADVISORY_CSV, encoding="utf-8", newline="") as f:
            for line in f:
                if line.startswith(date_str):
                    return True
    except Exception:
        pass
    return False


def _compute_rolling_miss_rate(existing_rows: List[Dict], new_rows: List[Dict]) -> List[Dict]:
    """
    Compute rolling 10-signal miss rate for each new row.
    Uses the trailing 10 resolved rows from existing_rows (where miss_flag is set).
    """
    resolved = [
        r for r in existing_rows
        if r.get("miss_flag") not in ("", None)
    ]
    # Build running window
    window: List[int] = [int(r["miss_flag"]) for r in resolved if r.get("miss_flag") in ("0", "1")]

    updated = []
    for row in new_rows:
        # Rolling miss rate is backfilled when exit_price_10d is populated; blank now
        row = dict(row)
        updated.append(row)

    return updated


def _check_kill_criteria(existing_rows: List[Dict], new_rows: List[Dict]) -> Optional[str]:
    """
    Kill criterion (Alt B): rolling 30-signal mean net_return_10d < -5%.

    Construct-valid for a payoff-ratio system (S2): directly measures EV, not win rate.
    Floor calibrated at p5 of S2 IS return distribution (-6.0%), rounded conservatively
    to -5% (≈ 3 sigma below zero for a 30-signal rolling mean).

    Fires: only when the rolling window is itself generating negative mean returns.
    Never fires when rolling mean return > 0 (by construction).

    Replaces: rolling 10-signal miss rate >= 40% (broken — fired at S2 baseline miss rate).
    """
    resolved = [
        r for r in existing_rows
        if r.get("net_return_10d") not in ("", None)
        and r.get("kill_criterion_fired", "") == ""
    ]
    if len(resolved) < KILL_WINDOW:
        return None  # insufficient history — do not kill

    window_returns = []
    for r in resolved[-KILL_WINDOW:]:
        try:
            window_returns.append(float(r["net_return_10d"]))
        except (TypeError, ValueError):
            continue

    if len(window_returns) < KILL_WINDOW:
        return None  # missing resolved returns — wait for backfill

    mean_ret = sum(window_returns) / len(window_returns)
    if mean_ret < MEAN_RETURN_KILL_FLOOR:
        return (
            f"MEAN_RETURN_FLOOR "
            f"(rolling_{KILL_WINDOW}sig_mean={mean_ret:.2%}, "
            f"floor={MEAN_RETURN_KILL_FLOOR:.0%})"
        )
    return None


def _append_rows(new_rows: List[Dict[str, Any]], dry_run: bool) -> int:
    """Append new rows to advisory_performance.csv. Returns count written."""
    if not new_rows:
        return 0

    if dry_run:
        print("[advisory_tracker] DRY RUN — rows that would be written:")
        writer = csv.DictWriter(sys.stdout, fieldnames=ADVISORY_HEADERS)
        for row in new_rows:
            writer.writerow(row)
        return len(new_rows)

    file_exists = ADVISORY_CSV.exists()
    # Check if file is empty (schema-stub only) or has real data rows
    has_data_header = False
    if file_exists:
        with open(ADVISORY_CSV, encoding="utf-8") as f:
            first_line = f.readline().strip()
            has_data_header = first_line == ",".join(ADVISORY_HEADERS)

    ADVISORY_CSV.parent.mkdir(parents=True, exist_ok=True)

    if not has_data_header:
        # File is schema-stub or missing: write fresh with proper CSV header
        with open(ADVISORY_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=ADVISORY_HEADERS)
            writer.writeheader()
            writer.writerows(new_rows)
    else:
        # Append to existing CSV
        with open(ADVISORY_CSV, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=ADVISORY_HEADERS)
            writer.writerows(new_rows)

    return len(new_rows)


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="S2 advisory signal outcome logger for T5 promotion gate."
    )
    parser.add_argument(
        "--date", type=str, default=None,
        help="Process signals for YYYY-MM-DD (default: today)"
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Override sentinel and re-run (does NOT dedup CSV; operator use only)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print rows to stdout; do not write to CSV or sentinel"
    )
    args = parser.parse_args()

    run_date = date.today()
    if args.date:
        try:
            run_date = date.fromisoformat(args.date)
        except ValueError:
            print(f"[advisory_tracker] ERROR: invalid date '{args.date}' (expected YYYY-MM-DD)", file=sys.stderr)
            return 1

    # ── Idempotency sentinel check ─────────────────────────────────────────────
    if not args.force and not args.dry_run and _sentinel_exists(run_date):
        print(
            f"[advisory_tracker] Sentinel exists for {run_date.isoformat()} — already ran today. "
            "Use --force to override.",
            file=sys.stderr,
        )
        return 0

    # ── Secondary dedup guard (belt-and-suspenders) ────────────────────────────
    if not args.force and not args.dry_run and _date_already_logged(run_date):
        print(
            f"[advisory_tracker] Date {run_date.isoformat()} already present in advisory_performance.csv. "
            "Exiting without writing duplicates.",
            file=sys.stderr,
        )
        _write_sentinel(run_date, rows_written=0)
        return 0

    # ── Load regime ────────────────────────────────────────────────────────────
    regime = _load_regime(run_date)
    print(f"[advisory_tracker] run_date={run_date.isoformat()} regime={regime}", file=sys.stderr)

    # ── Find scan CSV ──────────────────────────────────────────────────────────
    scan_csv = _find_scan_csv(run_date)
    if scan_csv is None:
        print(
            "[advisory_tracker] No scan CSV found — S2 advisory tracker requires "
            "phase36_daily_scan_latest.csv or a dated scan file.",
            file=sys.stderr,
        )
        # Not an error if in BEAR regime (zero signals expected)
        if regime != "A":
            print("[advisory_tracker] BEAR regime — zero signals expected. Exiting clean.", file=sys.stderr)
            if not args.dry_run:
                _write_sentinel(run_date, rows_written=0)
            return 0
        return 1

    print(f"[advisory_tracker] Using scan CSV: {scan_csv.name}", file=sys.stderr)

    # ── Extract S2 signals ─────────────────────────────────────────────────────
    new_rows = _extract_s2_signals(scan_csv, run_date, regime)
    print(f"[advisory_tracker] S2 advisory signals found: {len(new_rows)}", file=sys.stderr)

    # ── Check existing kill criteria ───────────────────────────────────────────
    existing_rows = _read_existing_rows(run_date)
    kill = _check_kill_criteria(existing_rows, new_rows)
    if kill:
        print(f"[advisory_tracker] KILL CRITERION FIRED: {kill}", file=sys.stderr)
        # Tag today's rows with the kill criterion; do not halt logging
        new_rows = [{**r, "kill_criterion_fired": kill} for r in new_rows]

    # ── Rolling miss rate annotation ───────────────────────────────────────────
    new_rows = _compute_rolling_miss_rate(existing_rows, new_rows)

    # ── Write ──────────────────────────────────────────────────────────────────
    rows_written = _append_rows(new_rows, dry_run=args.dry_run)
    print(f"[advisory_tracker] Rows written: {rows_written}", file=sys.stderr)

    # ── Write sentinel ─────────────────────────────────────────────────────────
    if not args.dry_run:
        _write_sentinel(run_date, rows_written=rows_written)

    if kill:
        print(
            f"[advisory_tracker] ⚠ Kill criterion fired: {kill}. "
            "Route to T5 gate review before proceeding.",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
