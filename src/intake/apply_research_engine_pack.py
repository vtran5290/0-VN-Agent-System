from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from src.intake.apply_consensus_pack import (
    MANUAL_INPUTS_PATH,
    WEEKLY_NOTES_PATH,
    _apply_manual_patch,
    _apply_weekly_notes_patch,
    _read_json,
    _safe_text,
    _write_json,
)


REPO = Path(__file__).resolve().parents[2]
DEFAULT_PACK_PATH = REPO / "data" / "raw" / "research_engine_pack.json"
MACHINE_DIR = REPO / "data" / "intake" / "machine"
ARCHIVE_DIR = MACHINE_DIR / "archive"
RESEARCH_FILES_DIR = MACHINE_DIR / "research_files"
LATEST_PATH = MACHINE_DIR / "research_pack_latest.json"
EXPECTED_EXTRACTION_MODE = "non_fund_intake_v1"


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return False


def _sanitize_doc_id(value: Any, idx: int) -> str:
    raw = _safe_text(value, f"F{idx:03d}")
    safe = "".join(ch for ch in raw if ch.isalnum() or ch in ("_", "-", "."))
    return safe or f"F{idx:03d}"


def _archive_pack(pack: Dict[str, Any], asof_date: str | None) -> Path:
    MACHINE_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    _write_json(LATEST_PATH, pack)
    asof = asof_date or "unknown_date"
    out = ARCHIVE_DIR / f"research_pack_{asof}_{_utc_stamp()}.json"
    _write_json(out, pack)
    return out


def _write_research_file_cards(pack: Dict[str, Any], asof_date: str | None) -> int:
    files = pack.get("research_files")
    if not isinstance(files, list):
        return 0
    asof = asof_date or "unknown_date"
    out_dir = RESEARCH_FILES_DIR / asof
    out_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for idx, row in enumerate(files, start=1):
        if not isinstance(row, dict):
            continue
        doc_id = _sanitize_doc_id(row.get("doc_id"), idx)
        out_path = out_dir / f"{doc_id}.json"
        payload = dict(row)
        payload.setdefault("doc_id", doc_id)
        payload.setdefault("asof_date", asof_date)
        _write_json(out_path, payload)
        written += 1
    return written


def apply_research_engine_pack(
    pack_path: Path,
    allow_null_overwrite: bool = False,
    strict_drift_guard: bool = False,
) -> None:
    pack = _read_json(pack_path, {})
    if not pack:
        raise ValueError(f"Invalid or empty research engine pack: {pack_path}")

    extraction_mode = _safe_text(pack.get("extraction_mode"), "")
    if extraction_mode and extraction_mode != EXPECTED_EXTRACTION_MODE:
        print(
            f"WARNING: extraction_mode={extraction_mode} (expected {EXPECTED_EXTRACTION_MODE}). "
            "Pack will still be applied."
        )

    drift_guard = pack.get("drift_guard") if isinstance(pack.get("drift_guard"), dict) else {}
    interpretation_added = _bool_value(drift_guard.get("interpretation_added"))
    decision_added = _bool_value(drift_guard.get("decision_added"))
    if interpretation_added or decision_added:
        msg = (
            "drift_guard indicates non-pure intake output "
            f"(interpretation_added={interpretation_added}, decision_added={decision_added})."
        )
        if strict_drift_guard:
            raise ValueError(msg)
        print(f"WARNING: {msg}")

    manual = _read_json(MANUAL_INPUTS_PATH, {})
    notes = _read_json(WEEKLY_NOTES_PATH, {})
    asof_date = _safe_text(pack.get("asof_date"), "")
    if asof_date:
        manual["asof_date"] = asof_date
        notes["asof_date"] = asof_date

    manual_patch = pack.get("manual_inputs_patch")
    if isinstance(manual_patch, dict):
        _apply_manual_patch(manual, manual_patch, allow_null_overwrite=allow_null_overwrite)

    weekly_notes_patch = pack.get("weekly_notes_patch")
    if isinstance(weekly_notes_patch, dict):
        _apply_weekly_notes_patch(notes, weekly_notes_patch)

    _write_json(MANUAL_INPUTS_PATH, manual)
    _write_json(WEEKLY_NOTES_PATH, notes)
    archived = _archive_pack(pack, asof_date or None)
    card_count = _write_research_file_cards(pack, asof_date or None)

    print(f"Applied research engine pack: {pack_path}")
    print(f"Manual patch mode: {'allow_null_overwrite' if allow_null_overwrite else 'non_destructive'}")
    print(f"Updated: {MANUAL_INPUTS_PATH}")
    print(f"Updated: {WEEKLY_NOTES_PATH}")
    print(f"Updated: {LATEST_PATH}")
    print(f"Archived: {archived}")
    print(f"Research file cards written: {card_count}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply non-fund Research Engine pack to manual_inputs + weekly_notes + machine archive."
    )
    parser.add_argument(
        "--pack",
        default=str(DEFAULT_PACK_PATH),
        help="Path to research engine pack JSON (default: data/raw/research_engine_pack.json).",
    )
    parser.add_argument(
        "--allow-null-overwrite",
        action="store_true",
        help="Allow null/unknown values in manual_inputs_patch to overwrite existing values.",
    )
    parser.add_argument(
        "--strict-drift-guard",
        action="store_true",
        help="Fail if drift_guard indicates interpretation/decision content in machine intake.",
    )
    args = parser.parse_args()
    apply_research_engine_pack(
        Path(args.pack),
        allow_null_overwrite=args.allow_null_overwrite,
        strict_drift_guard=args.strict_drift_guard,
    )


if __name__ == "__main__":
    main()
