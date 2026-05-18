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
PHASE36_LATEST_NAME = "phase36_daily_scan_latest.csv"
PHASE36_LEGACY_PRODUCTION_NAME = "phase36_daily_scan_sample.csv"
REQUIRED_SCAN_COLUMNS = frozenset({"as_of_date", "final_action", "strategy_classification"})


@dataclass
class ScanResolveResult:
    path: Path
    resolved_scan_source: str  # cli | env | config | latest
    scan_hash: str = ""
    is_sample: bool = False
    is_stale: bool = False
    scan_date: str = ""
    requested_date: str = ""
    effective_date: str = ""
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
    parts = {p.lower() for p in path.parts}
    name = path.name.lower()
    return (
        "intraday" in parts
        or "intraday" in name
        or name.startswith("phase36_intraday_scan")
    )


def _is_phase36_legacy_production_alias(path: Path, search_dir: Path) -> bool:
    if path.name != PHASE36_LEGACY_PRODUCTION_NAME:
        return False
    try:
        path.resolve().relative_to(search_dir.resolve())
    except ValueError:
        return False
    try:
        cols = set(pd.read_csv(path, nrows=0).columns)
    except Exception:
        return False
    return REQUIRED_SCAN_COLUMNS.issubset(cols)


def _phase36_preferred_path(search_dir: Path) -> Optional[Path]:
    latest = search_dir / PHASE36_LATEST_NAME
    if latest.exists():
        return latest
    legacy = search_dir / PHASE36_LEGACY_PRODUCTION_NAME
    if legacy.exists():
        return legacy
    return None


def _latest_phase_csv(search_dir: Path) -> Optional[Path]:
    if not search_dir.exists():
        return None
    p36 = _phase36_preferred_path(search_dir)
    if p36 is not None:
        return p36
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
        return (
            pd.to_datetime(df["as_of_date"], errors="coerce")
            .dt.strftime("%Y-%m-%d")
            .dropna()
            .unique()
            .tolist()
        )
    except Exception:
        return []


def resolve_scan(
    config: LiveTradingConfig,
    asof_date: str,
    cli_scan_path: Optional[Path] = None,
    *,
    test_mode: bool = False,
    search_dir: Optional[Path] = None,
    allow_sample: Optional[bool] = None,
    use_latest_scan_date: bool = False,
) -> ScanResolveResult:
    """Resolve scan CSV with priority: CLI path > env > config > phase36 latest > latest phase36/35/34."""
    warnings: List[str] = []
    errors: List[str] = []
    chosen: Optional[Path] = None
    source = ""
    sdir = search_dir or SCAN_SEARCH_DIR
    allow_sample_flag = config.allow_sample_scan if allow_sample is None else allow_sample

    if cli_scan_path is not None:
        chosen = Path(cli_scan_path)
        if not chosen.is_absolute():
            chosen = (REPO_ROOT / chosen).resolve()
        source = "cli"
    elif os.environ.get("PHASE36_DAILY_SCAN_PATH"):
        chosen = Path(os.environ["PHASE36_DAILY_SCAN_PATH"])
        source = "env"
    elif config.scan_csv_path and config.scan_csv_path.exists():
        chosen = config.scan_csv_path
        source = "config"
    else:
        latest = _latest_phase_csv(sdir)
        if latest:
            chosen = latest
            source = "latest"

    requested = asof_date[:10]
    effective = requested

    if chosen is None or not chosen.exists():
        return ScanResolveResult(
            path=config.scan_csv_path,
            resolved_scan_source=source or "none",
            requested_date=requested,
            effective_date=effective,
            errors=["No valid daily scan CSV found"],
            block_order_generation=True,
        )

    if _is_intraday_preview(chosen) and not test_mode:
        return ScanResolveResult(
            path=chosen,
            resolved_scan_source=source,
            requested_date=requested,
            effective_date=effective,
            errors=[f"Intraday preview scan blocked for OMS: {chosen.name}. Use EOD phase36 daily scan."],
            block_order_generation=True,
            metadata={"is_intraday_preview": True},
        )

    legacy_alias = _is_phase36_legacy_production_alias(chosen, sdir)
    is_sample = _is_sample_name(chosen)

    if legacy_alias:
        if not allow_sample_flag and not test_mode:
            return ScanResolveResult(
                path=chosen,
                resolved_scan_source=source,
                is_sample=True,
                requested_date=requested,
                effective_date=effective,
                errors=[
                    f"Phase36 legacy alias requires --allow-sample or use {PHASE36_LATEST_NAME}: {chosen.name}"
                ],
                block_order_generation=True,
                metadata={"legacy_phase36_alias": True},
            )
        warnings.append(
            f"Using Phase36 legacy production alias (sample-named file): {chosen.name}"
        )
        is_sample = False
    elif is_sample and not test_mode:
        return ScanResolveResult(
            path=chosen,
            resolved_scan_source=source,
            is_sample=True,
            requested_date=requested,
            effective_date=effective,
            errors=[
                f"Sample scan blocked: {chosen.name}. Use {PHASE36_LATEST_NAME} or Phase36 legacy with --allow-sample."
            ],
            block_order_generation=True,
        )

    scan_hash = _file_hash(chosen)
    dates = _scan_dates_in_file(chosen)
    scan_date = max(dates) if dates else ""
    calendar_stale = bool(dates) and requested not in dates

    if calendar_stale:
        reason = f"stale_scan_requested_{requested}_latest_{scan_date or 'unknown'}"
        warnings.append(f"asof {requested} not in scan dates (latest in file: {scan_date or 'unknown'})")
        if use_latest_scan_date and scan_date:
            effective = scan_date
            warnings.append(
                f"OPERATOR OVERRIDE: use_latest_scan_date - running with scan as_of_date {scan_date} "
                f"(requested calendar date was {requested})"
            )
        elif not test_mode:
            warnings.append(reason)

    block = bool(calendar_stale and not use_latest_scan_date and not test_mode)

    return ScanResolveResult(
        path=chosen,
        resolved_scan_source=source,
        scan_hash=scan_hash,
        is_sample=is_sample,
        is_stale=calendar_stale,
        scan_date=scan_date,
        requested_date=requested,
        effective_date=effective,
        block_order_generation=block,
        warnings=warnings,
        errors=errors,
        metadata={
            "resolved_scan_path": str(chosen),
            "resolved_scan_source": source,
            "scan_hash": scan_hash,
            "is_sample": is_sample,
            "is_stale": calendar_stale,
            "scan_date": scan_date,
            "requested_date": requested,
            "effective_date": effective,
            "use_latest_scan_date": use_latest_scan_date,
            "legacy_phase36_alias": legacy_alias,
            "allow_sample": bool(allow_sample_flag),
            "test_mode": bool(test_mode),
        },
    )
