"""
Master runner: fetch_global, fetch_vn_market, compute_dist_days, update manual_inputs.
Usage: python scripts/run_ingestion.py --all
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")
except ImportError:
    pass

LOG_DIR = REPO_ROOT / "logs"
LOG_FILE = LOG_DIR / "ingestion.log"


def _setup_logging() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def run_all(asof: str | None = None, force_vn_liquidity: bool = False) -> None:
    _setup_logging()
    log = logging.getLogger("run_ingestion")
    from scripts.update_manual_inputs import run as update_manual
    log.info("run_ingestion --all start")
    try:
        update_manual(asof, force_vn_liquidity=force_vn_liquidity)
        log.info("run_ingestion --all done")
    except Exception as e:
        log.exception("run_ingestion failed: %s", e)
        raise


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="VN Investment Terminal data ingestion")
    ap.add_argument("--all", action="store_true", help="Fetch global + VN market + dist days, update manual_inputs")
    ap.add_argument("--asof", default=None, help="Date YYYY-MM-DD")
    ap.add_argument("--force-vn-liquidity", action="store_true", help="Allow overwrite of VN liquidity fields")
    args = ap.parse_args()
    if not args.all:
        ap.print_help()
        sys.exit(0)
    run_all(args.asof, getattr(args, "force_vn_liquidity", False))
