"""Resolve Phase35/36 daily scan CSV path (fail-closed, no silent sample in prod)."""
from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from src.trading.config import REPO_ROOT, LiveTradingConfig

SCAN_SEARCH_DIR = REPO_ROOT / "data/research/portfolio_optimization/missing_work"
PHASE_PRIORITY = ("phase36", "phase35", "phase34")


@dataclass
class ScanResolveResult:
    path: Path
    resolved_scan_source: str  # cli | env | config | latest
    scan_hash: str = ""
    is_sample: bool = False
    is_stale: bool = False
    scan_date: str = ""
    block_order_generation: bool = False
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def blocked(self) -> bool:
        return bool(self.errors) or self.block_order_generation


def _file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def _is_sample_name(path: Path) -> bool:
    return "sample" in path.name.lower()


def _is_intraday_preview(path: Path) -> bool:
    """Intraday preview CSVs must not feed OMS / live workflow."""
    parts = {p.lower() for p in path.parts}
    name = path.name.lower()
    return (
        "intraday" in parts
        or "intraday" in name
        or name.startswith("phase36_intraday_scan")
    )


def _latest_phase_csv(search_dir: Path) -> Optional[Path]:
    if not search_dir.exists():
        return None
    for phase in PHASE_PRIORITY:
        pattern = re.compile(rf"^{re.escape(phase)}.*\.csv$", re.I)
        candidates = sorted(
            (p for p in search_dir.iterdir() if p.is_file() and pattern.match(p.name)),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if candidates:
            return candidates[0]
    return None


def _scan_dates_in_file(path: Path) -> List[str]:
    try:
        df = pd.read_csv(path, usecols=["as_of_date"], nrows=5000)
        if "as_of_date" not in df.columns:
            return []
        return pd.to_datetime(df["as_of_date"], errors="coerce").dt.strftime("%Y-%m-%d").dropna().unique().tolist()
    except Exception:
        return []


def resolve_scan(
    config: LiveTradingConfig,
    asof_date: str,
    cli_scan_path: Optional[Path] = None,
    *,
    test_mode: bool = False,
    search_dir: Optional[Path] = None,
) -> ScanResolveResult:
    """Resolve scan CSV with priority: CLI > env > config > latest phase36/35/34."""
    warnings: List[str] = []
    errors: List[str] = []
    chosen: Optional[Path] = None
    source = ""

    if cli_scan_path is not None:
        chosen = Path(cli_scan_path)
        source = "cli"
    elif os.environ.get("PHASE36_DAILY_SCAN_PATH"):
        chosen = Path(os.environ["PHASE36_DAILY_SCAN_PATH"])
        source = "env"
    elif config.scan_csv_path and config.scan_csv_path.exists():
        chosen = config.scan_csv_path
        source = "config"
    else:
        latest = _latest_phase_csv(search_dir or SCAN_SEARCH_DIR)
        if latest:
            chosen = latest
            source = "latest"

    if chosen is None or not chosen.exists():
        return ScanResolveResult(
            path=config.scan_csv_path,
            resolved_scan_source=source or "none",
            errors=["No valid daily scan CSV found"],
            block_order_generation=True,
        )

    is_intraday = _is_intraday_preview(chosen)
    if is_intraday and not test_mode:
        return ScanResolveResult(
            path=chosen,
            resolved_scan_source=source,
            errors=[f"Intraday preview scan blocked for OMS: {chosen.name}. Use EOD phase36 daily scan."],
            block_order_generation=True,
            metadata={"is_intraday_preview": True},
        )

    is_sample = _is_sample_name(chosen)
    if is_sample and not config.allow_sample_scan and not test_mode:
        return ScanResolveResult(
            path=chosen,
            resolved_scan_source=source,
            is_sample=True,
            errors=[f"Sample scan blocked: {chosen.name}. Set allow_sample_scan=true to override."],
            block_order_generation=True,
        )
    if is_sample and config.allow_sample_scan:
        warnings.append(f"Using sample scan: {chosen.name}")

    scan_hash = _file_hash(chosen)
    dates = _scan_dates_in_file(chosen)
    scan_date = max(dates) if dates else ""
    asof = asof_date[:10]
    is_stale = bool(dates) and asof not in dates
    if is_stale:
        warnings.append(f"asof {asof} not in scan dates (latest in file: {scan_date or 'unknown'})")
        if not test_mode and not config.allow_sample_scan:
            # stale non-sample: block generation unless sample allowed for fixtures
            pass  # WARN only for paper; block handled below via config

    block = False
    if is_stale and not test_mode:
        block = True
        warnings.append("Stale scan for asof date — BLOCK_ORDER_GENERATION")

    return ScanResolveResult(
        path=chosen,
        resolved_scan_source=source,
        scan_hash=scan_hash,
        is_sample=is_sample,
        is_stale=is_stale,
        scan_date=scan_date,
        block_order_generation=block,
        warnings=warnings,
        errors=errors,
        metadata={
            "resolved_scan_path": str(chosen),
            "resolved_scan_source": source,
            "scan_hash": scan_hash,
            "is_sample": is_sample,
            "is_stale": is_stale,
            "scan_date": scan_date,
        },
    )
