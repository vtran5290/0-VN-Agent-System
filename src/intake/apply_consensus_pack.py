from __future__ import annotations

import argparse
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Tuple


REPO = Path(__file__).resolve().parents[2]
DEFAULT_PACK_PATH = REPO / "data" / "raw" / "consensus_pack.json"
MANUAL_INPUTS_PATH = REPO / "data" / "raw" / "manual_inputs.json"
WEEKLY_NOTES_PATH = REPO / "data" / "raw" / "weekly_notes.json"
SMART_MONEY_WEEKLY_DIR = REPO / "data" / "smart_money" / "weekly"

_UNKNOWN_TOKENS = {"", "unknown", "null", "none", "n/a", "na"}
_FED_TONES = {"dovish", "neutral", "hawkish", "unknown"}
_LIQUIDITY_STATES = {"easing", "tight", "unknown"}
_INTAKE_TYPES = {"macro_report", "sector_report", "company_report", "policy_report"}
EXPECTED_EXTRACTION_MODE = "smart_money_consensus_v1"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")

_TOP_LEVEL_ALLOWED = {
    "asof_date",
    "extraction_mode",
    "drift_guard",
    "report_month_ref",
    "smart_money_month_ref",
    "smart_money_signals",
    "manual_inputs_patch",
    "weekly_notes_patch",
    "consensus_card",
    "unknown_fields",
    "sources",
}
_TOP_LEVEL_REQUIRED = {
    "asof_date",
    "extraction_mode",
    "drift_guard",
    "manual_inputs_patch",
    "weekly_notes_patch",
}
_WEEKLY_NOTES_ALLOWED = {"policy_facts", "earnings_facts", "broker_notes", "intake_takeaways"}
_SMART_MONEY_SIGNALS_ALLOWED = {
    "mega_consensus",
    "sector_consensus",
    "crowding_score",
    "risk_on_score",
    "policy_alignment_score",
    "risk_flags",
}
_MANUAL_PATCH_ALLOWED = {"global", "vietnam", "market", "overrides"}

_MANUAL_NUMERIC_FIELDS = {
    ("global", "ust_2y"),
    ("global", "ust_10y"),
    ("global", "dxy"),
    ("global", "cpi_yoy"),
    ("global", "nfp"),
    ("vietnam", "omo_net"),
    ("vietnam", "interbank_on"),
    ("vietnam", "credit_growth_yoy"),
    ("vietnam", "fx_usd_vnd"),
    ("market", "vnindex_level"),
    ("market", "distribution_days_rolling_20"),
}


def _read_json(path: Path, default: Dict[str, Any]) -> Dict[str, Any]:
    if not path.exists():
        return dict(default)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else dict(default)
    except (OSError, json.JSONDecodeError):
        return dict(default)


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _norm_unknown_token(value: Any) -> Any:
    if isinstance(value, str) and value.strip().lower() in _UNKNOWN_TOKENS:
        return None
    return value


def _coerce_number(value: Any) -> float | int | None:
    value = _norm_unknown_token(value)
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        text = value.strip().replace(",", "")
        if not text:
            return None
        try:
            if "." in text:
                return float(text)
            return int(text)
        except ValueError:
            return None
    return None


def _safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _safe_date(value: Any) -> str | None:
    value = _norm_unknown_token(value)
    if value is None:
        return None
    text = _safe_text(value)
    return text if text else None


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return False


def _ensure_manual_shape(payload: Dict[str, Any]) -> None:
    payload.setdefault("global", {})
    payload.setdefault("vietnam", {})
    payload.setdefault("market", {})
    payload.setdefault("overrides", {})


def _append_error(errors: List[str], condition: bool, message: str) -> None:
    if condition:
        errors.append(message)


def _validate_pack_schema(pack: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []

    unknown_top = sorted(set(pack.keys()) - _TOP_LEVEL_ALLOWED)
    if unknown_top:
        errors.append(f"Unknown top-level field(s): {', '.join(unknown_top)}")

    missing_required = sorted(k for k in _TOP_LEVEL_REQUIRED if k not in pack)
    if missing_required:
        errors.append(f"Missing required field(s): {', '.join(missing_required)}")

    asof_date = _safe_text(pack.get("asof_date"), "")
    _append_error(errors, not asof_date, "asof_date is required and cannot be empty.")
    if asof_date and not _DATE_RE.match(asof_date):
        errors.append("asof_date must match YYYY-MM-DD.")

    extraction_mode = _safe_text(pack.get("extraction_mode"), "")
    _append_error(errors, extraction_mode != EXPECTED_EXTRACTION_MODE, f"extraction_mode must be {EXPECTED_EXTRACTION_MODE}.")

    drift_guard = pack.get("drift_guard")
    _append_error(errors, not isinstance(drift_guard, dict), "drift_guard must be an object.")
    if isinstance(drift_guard, dict):
        if "interpretation_added" not in drift_guard or "decision_added" not in drift_guard:
            errors.append("drift_guard requires interpretation_added and decision_added.")
        if "interpretation_added" in drift_guard and not isinstance(drift_guard.get("interpretation_added"), bool):
            errors.append("drift_guard.interpretation_added must be boolean.")
        if "decision_added" in drift_guard and not isinstance(drift_guard.get("decision_added"), bool):
            errors.append("drift_guard.decision_added must be boolean.")
        if _bool_value(drift_guard.get("interpretation_added")) or _bool_value(drift_guard.get("decision_added")):
            warnings.append("drift_guard indicates interpretation/decision content in intake.")

    report_month_ref = _safe_text(pack.get("report_month_ref"), "")
    smart_month_ref = _safe_text(pack.get("smart_money_month_ref"), "")
    if report_month_ref and not _MONTH_RE.match(report_month_ref):
        errors.append("report_month_ref must match YYYY-MM.")
    if smart_month_ref and not _MONTH_RE.match(smart_month_ref):
        errors.append("smart_money_month_ref must match YYYY-MM.")
    if report_month_ref and smart_month_ref and report_month_ref != smart_month_ref:
        errors.append("report_month_ref and smart_money_month_ref must be identical when both are provided.")

    manual_patch = pack.get("manual_inputs_patch")
    _append_error(errors, not isinstance(manual_patch, dict), "manual_inputs_patch must be an object.")
    if isinstance(manual_patch, dict):
        unknown_manual = sorted(set(manual_patch.keys()) - _MANUAL_PATCH_ALLOWED)
        if unknown_manual:
            errors.append(f"manual_inputs_patch contains unknown section(s): {', '.join(unknown_manual)}")
        for section in manual_patch:
            if section in _MANUAL_PATCH_ALLOWED and not isinstance(manual_patch.get(section), dict):
                errors.append(f"manual_inputs_patch.{section} must be an object.")

    weekly_patch = pack.get("weekly_notes_patch")
    _append_error(errors, not isinstance(weekly_patch, dict), "weekly_notes_patch must be an object.")
    if isinstance(weekly_patch, dict):
        unknown_weekly = sorted(set(weekly_patch.keys()) - _WEEKLY_NOTES_ALLOWED)
        if unknown_weekly:
            errors.append(f"weekly_notes_patch contains unknown key(s): {', '.join(unknown_weekly)}")
        for key in ("policy_facts", "earnings_facts", "broker_notes", "intake_takeaways"):
            if key in weekly_patch:
                value = weekly_patch.get(key)
                if not isinstance(value, list):
                    errors.append(f"weekly_notes_patch.{key} must be a list.")
                elif len(value) > 5:
                    errors.append(f"weekly_notes_patch.{key} exceeds max length 5.")

    smart_signals = pack.get("smart_money_signals")
    if smart_signals is not None:
        if not isinstance(smart_signals, dict):
            errors.append("smart_money_signals must be an object when provided.")
        else:
            unknown_signal_keys = sorted(set(smart_signals.keys()) - _SMART_MONEY_SIGNALS_ALLOWED)
            if unknown_signal_keys:
                errors.append(f"smart_money_signals contains unknown key(s): {', '.join(unknown_signal_keys)}")
            for key in ("mega_consensus", "sector_consensus", "risk_flags"):
                if key in smart_signals:
                    value = smart_signals.get(key)
                    if not isinstance(value, list):
                        errors.append(f"smart_money_signals.{key} must be a list.")
                    elif len(value) > 5:
                        errors.append(f"smart_money_signals.{key} exceeds max length 5.")

    for key in ("unknown_fields", "sources"):
        if key in pack and not isinstance(pack.get(key), list):
            errors.append(f"{key} must be a list when provided.")

    return errors, warnings


def _sync_month_ref_aliases(pack: Dict[str, Any]) -> str:
    report_month_ref = _safe_text(pack.get("report_month_ref"), "")
    smart_month_ref = _safe_text(pack.get("smart_money_month_ref"), "")
    month_ref = smart_month_ref or report_month_ref
    if month_ref:
        pack["smart_money_month_ref"] = month_ref
        pack["report_month_ref"] = month_ref
    return month_ref


def _apply_manual_patch(manual: Dict[str, Any], patch: Dict[str, Any], allow_null_overwrite: bool = False) -> None:
    _ensure_manual_shape(manual)
    for section in ("global", "vietnam", "market", "overrides"):
        src = patch.get(section)
        if not isinstance(src, dict):
            continue
        dst = manual.setdefault(section, {})
        for key, value in src.items():
            if (section, key) in _MANUAL_NUMERIC_FIELDS:
                coerced = _coerce_number(value)
                if coerced is None and not allow_null_overwrite:
                    continue
                dst[key] = coerced
                continue
            if section == "global" and key == "fed_tone":
                tone = _safe_text(value, "unknown").lower()
                normalized_tone = tone if tone in _FED_TONES else "unknown"
                if normalized_tone == "unknown" and not allow_null_overwrite:
                    continue
                dst[key] = normalized_tone
                continue
            if section == "overrides" and key in ("global_liquidity", "vn_liquidity"):
                state = _safe_text(value, "unknown").lower()
                normalized_state = state if state in _LIQUIDITY_STATES else "unknown"
                if normalized_state == "unknown" and not allow_null_overwrite:
                    continue
                dst[key] = normalized_state
                continue
            normalized = _norm_unknown_token(value)
            if normalized is None and not allow_null_overwrite:
                continue
            dst[key] = normalized


def _norm_policy_items(items: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not isinstance(items, list):
        return out
    for item in items:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "source": _safe_text(item.get("source"), "consensus_pack"),
                "title": _safe_text(item.get("title"), "Unknown"),
                "date": _safe_date(item.get("date")),
                "summary": _safe_text(item.get("summary"), "Unknown"),
            }
        )
    return out


def _norm_earnings_items(items: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not isinstance(items, list):
        return out
    for item in items:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "source": _safe_text(item.get("source"), "consensus_pack"),
                "ticker": _safe_text(item.get("ticker"), "Unknown"),
                "period": _safe_text(item.get("period"), "Unknown"),
                "summary": _safe_text(item.get("summary"), "Unknown"),
            }
        )
    return out


def _norm_broker_items(items: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not isinstance(items, list):
        return out
    for item in items:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "source": _safe_text(item.get("source"), "consensus_pack"),
                "firm": _safe_text(item.get("firm"), "Unknown"),
                "ticker": _safe_text(item.get("ticker"), "Unknown"),
                "summary": _safe_text(item.get("summary"), "Unknown"),
            }
        )
    return out


def _norm_takeaways(items: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not isinstance(items, list):
        return out
    for item in items:
        if not isinstance(item, dict):
            continue
        typ = _safe_text(item.get("type"), "company_report")
        typ = typ if typ in _INTAKE_TYPES else "company_report"
        bullets_raw = item.get("summary_bullets")
        bullets: List[str] = []
        if isinstance(bullets_raw, list):
            for bullet in bullets_raw:
                text = _safe_text(bullet)
                if text:
                    bullets.append(text)
        out.append({"type": typ, "summary_bullets": bullets})
    return out


def _apply_weekly_notes_patch(notes: Dict[str, Any], patch: Dict[str, Any]) -> None:
    if "policy_facts" in patch:
        notes["policy_facts"] = _norm_policy_items(patch.get("policy_facts"))
    if "earnings_facts" in patch:
        notes["earnings_facts"] = _norm_earnings_items(patch.get("earnings_facts"))
    if "broker_notes" in patch:
        notes["broker_notes"] = _norm_broker_items(patch.get("broker_notes"))
    if "intake_takeaways" in patch:
        notes["intake_takeaways"] = _norm_takeaways(patch.get("intake_takeaways"))


def _flatten(prefix: str, value: Any, out: Dict[str, Any]) -> None:
    if isinstance(value, dict):
        for key in sorted(value.keys()):
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            _flatten(child_prefix, value[key], out)
    else:
        out[prefix] = value


def _diff_changes(before: Dict[str, Any], after: Dict[str, Any]) -> List[Tuple[str, Any, Any]]:
    flat_before: Dict[str, Any] = {}
    flat_after: Dict[str, Any] = {}
    _flatten("", before, flat_before)
    _flatten("", after, flat_after)
    keys = sorted(set(flat_before.keys()) | set(flat_after.keys()))
    changes: List[Tuple[str, Any, Any]] = []
    for key in keys:
        b = flat_before.get(key)
        a = flat_after.get(key)
        if b != a:
            changes.append((key, b, a))
    return changes


def _print_changes(label: str, changes: List[Tuple[str, Any, Any]], max_rows: int = 120) -> None:
    print(f"{label}: {len(changes)} changed field(s)")
    if not changes:
        return
    for idx, (path, old, new) in enumerate(changes):
        if idx >= max_rows:
            print(f"  ... truncated ({len(changes) - max_rows} more)")
            break
        print(f"  - {path}: {json.dumps(old, ensure_ascii=False)} -> {json.dumps(new, ensure_ascii=False)}")


def _persist_smart_money_snapshot(pack: Dict[str, Any], asof_date: str | None) -> None:
    payload = {
        "asof_date": asof_date,
        "extraction_mode": _safe_text(pack.get("extraction_mode"), ""),
        "drift_guard": pack.get("drift_guard", {}),
        "smart_money_month_ref": _safe_text(pack.get("smart_money_month_ref"), ""),
        "report_month_ref": _safe_text(pack.get("report_month_ref"), ""),
        "smart_money_signals": pack.get("smart_money_signals"),
        "consensus_card": pack.get("consensus_card"),
        "sources": pack.get("sources", []),
        "unknown_fields": pack.get("unknown_fields", []),
    }
    SMART_MONEY_WEEKLY_DIR.mkdir(parents=True, exist_ok=True)
    latest_path = SMART_MONEY_WEEKLY_DIR / "smart_money_consensus_latest.json"
    _write_json(latest_path, payload)
    if asof_date:
        dated_path = SMART_MONEY_WEEKLY_DIR / f"smart_money_consensus_{asof_date}.json"
        _write_json(dated_path, payload)


def apply_consensus_pack(
    pack_path: Path,
    allow_null_overwrite: bool = False,
    dry_run: bool = False,
    skip_schema_validate: bool = False,
) -> None:
    pack = _read_json(pack_path, {})
    if not pack:
        raise ValueError(f"Invalid or empty consensus pack: {pack_path}")

    _sync_month_ref_aliases(pack)

    if not skip_schema_validate:
        errors, warnings = _validate_pack_schema(pack)
        for warning in warnings:
            print(f"WARNING: {warning}")
        if errors:
            raise ValueError("Schema validation failed:\n- " + "\n- ".join(errors))

    manual_before = _read_json(MANUAL_INPUTS_PATH, {})
    notes_before = _read_json(WEEKLY_NOTES_PATH, {})
    manual_after = deepcopy(manual_before)
    notes_after = deepcopy(notes_before)

    asof_date = _safe_text(pack.get("asof_date"), "")
    if asof_date:
        manual_after["asof_date"] = asof_date
        notes_after["asof_date"] = asof_date

    manual_patch = pack.get("manual_inputs_patch")
    if isinstance(manual_patch, dict):
        _apply_manual_patch(manual_after, manual_patch, allow_null_overwrite=allow_null_overwrite)

    notes_patch = pack.get("weekly_notes_patch")
    if isinstance(notes_patch, dict):
        _apply_weekly_notes_patch(notes_after, notes_patch)

    manual_changes = _diff_changes(manual_before, manual_after)
    notes_changes = _diff_changes(notes_before, notes_after)

    if dry_run:
        print(f"DRY RUN: {pack_path}")
        print(f"Manual patch mode: {'allow_null_overwrite' if allow_null_overwrite else 'non_destructive'}")
        _print_changes("manual_inputs preview", manual_changes)
        _print_changes("weekly_notes preview", notes_changes)
        print("No files were written.")
        return

    _write_json(MANUAL_INPUTS_PATH, manual_after)
    _write_json(WEEKLY_NOTES_PATH, notes_after)
    _persist_smart_money_snapshot(pack, asof_date or None)

    print(f"Applied consensus pack: {pack_path}")
    print(f"Manual patch mode: {'allow_null_overwrite' if allow_null_overwrite else 'non_destructive'}")
    _print_changes("manual_inputs", manual_changes)
    _print_changes("weekly_notes", notes_changes)
    print(f"Updated: {MANUAL_INPUTS_PATH}")
    print(f"Updated: {WEEKLY_NOTES_PATH}")
    print(f"Wrote snapshot: {SMART_MONEY_WEEKLY_DIR / 'smart_money_consensus_latest.json'}")
    if asof_date:
        print(f"Wrote snapshot: {SMART_MONEY_WEEKLY_DIR / f'smart_money_consensus_{asof_date}.json'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply consensus pack to manual_inputs + weekly_notes.")
    parser.add_argument(
        "--pack",
        default=str(DEFAULT_PACK_PATH),
        help="Path to consensus pack JSON (default: data/raw/consensus_pack.json).",
    )
    parser.add_argument(
        "--allow-null-overwrite",
        action="store_true",
        help="Allow null/unknown values in manual_inputs_patch to overwrite existing values.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview patch changes without writing files.",
    )
    parser.add_argument(
        "--skip-schema-validate",
        action="store_true",
        help="Skip schema validation (not recommended).",
    )
    args = parser.parse_args()
    apply_consensus_pack(
        Path(args.pack),
        allow_null_overwrite=args.allow_null_overwrite,
        dry_run=args.dry_run,
        skip_schema_validate=args.skip_schema_validate,
    )


if __name__ == "__main__":
    main()
