"""
Full weekly pipeline: fetch latest inputs → weekly MD/JSON → normalize → HTML dashboard.

Order:
  1. update_manual_inputs: global (FRED + DXY fallback), Vietnam liquidity (SBV scrape),
     market left empty so src.report.weekly uses FireAnt macro snapshot for VN index/dist.
  2. src.report.weekly --render
  3. scripts.ingest.run_weekly_update (normalize processed JSON)
  4. scripts.reporting.render_weekly_report (reports/latest + archive)

Env:
  FRED_API_KEY — optional but recommended for UST 2Y/10Y, CPI YoY, NFP (see scripts/fetch_global.py).
  FIREANT_TOKEN — used by FireAnt client inside weekly (if not in env, client may fail per repo setup).

OMO net: SBV page is often JS-rendered; omo_net may stay null — fill manually if needed.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

try:
    # Ensure .env values are visible to os.getenv(...) in child processes.
    from dotenv import load_dotenv

    load_dotenv(REPO / ".env", override=False)
except Exception:
    # dotenv is optional; if unavailable, scripts will rely on system env vars.
    pass


def _run(cmd: list[str], timeout: int) -> int:
    print(f"\n>>> {' '.join(cmd)}\n")
    r = subprocess.run(cmd, cwd=REPO, timeout=timeout)
    return r.returncode


def main() -> int:
    ap = argparse.ArgumentParser(description="Weekly full fetch + report + HTML")
    ap.add_argument("--asof", default=None, help="As-of date YYYY-MM-DD (default: today)")
    ap.add_argument("--skip-fetch", action="store_true", help="Skip update_manual_inputs (use current manual_inputs.json)")
    ap.add_argument("--skip-weekly-md", action="store_true", help="Skip src.report.weekly --render")
    ap.add_argument("--no-validate", action="store_true", help="Pass --no-validate to run_weekly_update")
    args = ap.parse_args()

    asof = args.asof or date.today().isoformat()
    py = sys.executable

    print("=== Weekly full fetch (latest data for report) ===", flush=True)
    print(
        f"asof={asof}  |  FRED_API_KEY={'set' if os.getenv('FRED_API_KEY') else 'NOT SET (UST/CPI/NFP may stay from file)'}",
        flush=True,
    )
    print(f"  |  FIREANT_TOKEN={'set' if os.getenv('FIREANT_TOKEN') else 'NOT SET'}", flush=True)

    if not args.skip_fetch:
        rc = _run(
            [
                py,
                str(REPO / "scripts" / "update_manual_inputs.py"),
                "--asof",
                asof,
                "--force-vn-liquidity",
                "--skip-vn-market",
            ],
            timeout=180,
        )
        if rc != 0:
            print("update_manual_inputs failed.")
            return rc
    else:
        print("\n>>> (skipped) update_manual_inputs\n")

    if not args.skip_weekly_md:
        rc = _run([py, "-m", "src.report.weekly", "--render"], timeout=180)
        if rc != 0:
            print("src.report.weekly failed.")
            return rc
    else:
        print("\n>>> (skipped) src.report.weekly --render\n")

    # Weekly already ran above; ingest only normalizes decision JSON → processed + validate
    wargs = [py, "-m", "scripts.ingest.run_weekly_update", "--skip-weekly"]
    if args.no_validate:
        wargs.append("--no-validate")
    rc = _run(wargs, timeout=180)
    if rc != 0:
        print("run_weekly_update failed.")
        return rc

    rc = _run([py, "-m", "scripts.reporting.render_weekly_report"], timeout=120)
    if rc != 0:
        print("render_weekly_report failed.")
        return rc

    print("\n=== Done ===")
    print("  data/raw/manual_inputs.json")
    print("  data/decision/weekly_report.md, weekly_report.json")
    print("  data/processed/weekly_report.json")
    print("  reports/latest/index.html")
    print(f"  reports/archive/{asof}/index.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
