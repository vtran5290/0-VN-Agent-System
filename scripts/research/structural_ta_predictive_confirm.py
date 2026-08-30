"""Confirmation gate for Structural TA predictive loop (RESEARCH ONLY).

ChatGPT REDIRECT 2026-08-29 (Confirm Decision): F5/F6 stay sealed until this gate
is identity-bound, ex-VIN primary, paired vs CLI baseline, and one-shot.

Does not modify vn_ta_fireant_cli / OMS / final_action.
"""
from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from scripts.research.structural_ta_predictive_core import (
    DEFAULT_BOOTSTRAP_SEED,
    EX_VIN,
    FOLDS_YAML,
    date_level_ic_and_spread,
    filter_outcome_contained,
    git_identifier,
    load_canonical_folds,
    moving_block_bootstrap_mean,
    sha256_file,
    spec_hash,
)

CONFIRMATION_METRICS_NAME = "confirmation_metrics.json"
CONFIRMATION_RECEIPT_NAME = "confirmation_receipt.json"
CONFIRM_PREFLIGHT_NAME = "confirm_preflight.json"
CONFIRM_LOCK_NAME = "confirmation_write.lock"
CONFIRMATION_SPENT_NAME = "confirmation_spent.json"
FROZEN_CANDIDATE_NAME = "FROZEN_CANDIDATE.json"
F6_LABEL = "mixed/VIN_distorted"
SCORE_LOOP_MODULE = Path(__file__).resolve().parent / "structural_ta_predictive_score_loop.py"
CORE_MODULE = Path(__file__).resolve().parent / "structural_ta_predictive_core.py"

IDENTITY_SNAPSHOT_KEYS: Sequence[str] = (
    "candidate_spec_hash",
    "feature_parquet_sha256",
    "panel_sha256",
    "folds_yaml_sha256",
    "folds_version",
    "core_sha256",
    "git",
    "candidate_observations_sha256",
    "baseline_observations_sha256",
    "confirm_module_sha256",
    "score_loop_sha256",
    "baseline_iter_dir",
    "baseline_spec_hash",
)

# Gate declared after development disclosure (council caveat).
GATE_POST_HOC_CAVEAT = (
    "confirmation_gate_declared_after_development_disclosure"
)


def gate_code_hashes() -> Dict[str, str]:
    return {
        "confirm_module_sha256": sha256_file(Path(__file__)),
        "score_loop_sha256": sha256_file(SCORE_LOOP_MODULE),
        "core_sha256": sha256_file(CORE_MODULE),
    }


def observations_parquet_sha256(path: Path) -> str:
    return sha256_file(path)


def atomic_json_write(path: Path, obj: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(
        json.dumps(obj, indent=2, default=str, allow_nan=False),
        encoding="utf-8",
    )
    os.replace(str(tmp), str(path))


def confirm_preflight_file_sha256(iter_dir: Path) -> str:
    path = iter_dir / CONFIRM_PREFLIGHT_NAME
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}")
    return sha256_file(path)


def assert_approved_preflight_hash(iter_dir: Path, approved_sha256: str) -> str:
    actual = confirm_preflight_file_sha256(iter_dir)
    if actual != approved_sha256:
        raise ValueError(
            f"approved-preflight-sha256 mismatch: arg={approved_sha256} file={actual}"
        )
    return actual


def _spent_path(iter_dir: Path) -> Path:
    return iter_dir / CONFIRMATION_SPENT_NAME


def confirmation_holdout_spent(iter_dir: Path) -> bool:
    return _spent_path(iter_dir).exists()


def claim_confirmation_slot(iter_dir: Path) -> Path:
    """Exclusive create — refuses races, prior disclosure, or spent holdout."""
    metrics_path = iter_dir / CONFIRMATION_METRICS_NAME
    receipt_path = iter_dir / CONFIRMATION_RECEIPT_NAME
    lock_path = iter_dir / CONFIRM_LOCK_NAME
    spent_path = _spent_path(iter_dir)
    if spent_path.exists():
        raise FileExistsError(
            f"Confirmation holdout SPENT ({CONFIRMATION_SPENT_NAME}). Retry forbidden."
        )
    if metrics_path.exists() or receipt_path.exists():
        raise FileExistsError(
            f"One-shot confirm refused: {metrics_path.name} or "
            f"{receipt_path.name} already exists"
        )
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
    except FileExistsError:
        raise FileExistsError(
            f"Confirmation slot locked or taken: {lock_path}"
        ) from None
    return lock_path


def finalize_confirmation_bundle(
    iter_dir: Path,
    lock_path: Path,
    artifact: Dict[str, Any],
    receipt: Dict[str, Any],
) -> Tuple[Path, Path]:
    """Write metrics + receipt atomically; receipt binds metrics file SHA256."""
    metrics_path = iter_dir / CONFIRMATION_METRICS_NAME
    receipt_path = iter_dir / CONFIRMATION_RECEIPT_NAME
    if metrics_path.exists() or receipt_path.exists():
        raise FileExistsError(
            f"Confirmation artifact already exists: {metrics_path.name} or "
            f"{receipt_path.name}"
        )
    atomic_json_write(metrics_path, artifact)
    receipt_out = dict(receipt)
    receipt_out["confirmation_metrics_sha256"] = sha256_file(metrics_path)
    atomic_json_write(receipt_path, receipt_out)
    if lock_path.exists():
        lock_path.unlink()
    return metrics_path, receipt_path


def mark_confirmation_spent(
    iter_dir: Path,
    lock_path: Path,
    *,
    reason: str,
    approved_preflight_sha256: Optional[str] = None,
) -> Path:
    """Permanent marker after slot claimed — holdout cannot be re-opened."""
    spent_path = _spent_path(iter_dir)
    metrics_path = iter_dir / CONFIRMATION_METRICS_NAME
    receipt_path = iter_dir / CONFIRMATION_RECEIPT_NAME
    for p in (metrics_path, receipt_path):
        if p.exists():
            p.unlink()
    body = {
        "schema_version": "2.3_confirmation_spent",
        "label": "RESEARCH_ONLY_NOT_PRODUCTION",
        "status": "FAILED_AFTER_OPEN",
        "holdout_spent": True,
        "retry_forbidden": True,
        "reason": reason,
        "approved_preflight_sha256": approved_preflight_sha256,
        "gate_caveat": GATE_POST_HOC_CAVEAT,
    }
    atomic_json_write(spent_path, body)
    if lock_path.exists():
        lock_path.unlink()
    return spent_path


def write_confirmation_bundle(
    iter_dir: Path,
    artifact: Dict[str, Any],
    receipt: Dict[str, Any],
) -> Tuple[Path, Path]:
    """Claim slot then finalize (for tests — production uses claim-before-IC)."""
    lock_path = claim_confirmation_slot(iter_dir)
    try:
        return finalize_confirmation_bundle(iter_dir, lock_path, artifact, receipt)
    except Exception as exc:
        mark_confirmation_spent(
            iter_dir,
            lock_path,
            reason=f"bundle_finalize_failed: {exc}",
            approved_preflight_sha256=receipt.get("approved_preflight_sha256"),
        )
        raise


def _normalize_path(p: Path) -> Path:
    try:
        return p.resolve()
    except OSError:
        return p.absolute()


def load_frozen_candidate(out_dir: Path) -> Dict[str, Any]:
    path = out_dir / FROZEN_CANDIDATE_NAME
    if not path.exists():
        raise FileNotFoundError(f"Missing approved snapshot {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_confirm_preflight(iter_dir: Path) -> Dict[str, Any]:
    path = iter_dir / CONFIRM_PREFLIGHT_NAME
    if not path.exists():
        raise FileNotFoundError(
            f"Missing approved preflight snapshot {path}. Run confirm-preflight first."
        )
    return json.loads(path.read_text(encoding="utf-8"))


PATH_IDENTITY_KEYS = frozenset({"iter_dir", "baseline_iter_dir"})


def _identity_field_equal(key: str, current: Any, approved: Any) -> bool:
    if key in PATH_IDENTITY_KEYS:
        try:
            return _normalize_path(Path(str(current))) == _normalize_path(Path(str(approved)))
        except (TypeError, ValueError):
            return False
    return current == approved


def identity_snapshot_drift(
    current: Dict[str, Any],
    approved: Dict[str, Any],
    keys: Sequence[str] = IDENTITY_SNAPSHOT_KEYS,
) -> List[str]:
    drift: List[str] = []
    for k in keys:
        if not _identity_field_equal(k, current.get(k), approved.get(k)):
            drift.append(
                f"{k}: approved={approved.get(k)!r} current={current.get(k)!r}"
            )
    return drift


def enforce_approved_snapshot(
    *,
    out_dir: Path,
    iter_dir: Path,
    freeze_hash: str,
    baseline_iter_dir: Path,
    baseline_spec_hash: str,
    current_identity: Dict[str, Any],
    approved_preflight_sha256: str,
) -> Dict[str, Any]:
    """Hard refuse if reviewed freeze/preflight snapshots do not match live inputs."""
    assert_approved_preflight_hash(iter_dir, approved_preflight_sha256)
    frozen = load_frozen_candidate(out_dir)
    preflight = load_confirm_preflight(iter_dir)

    if frozen.get("spec_hash") != freeze_hash:
        raise ValueError(
            f"freeze_hash {freeze_hash} != FROZEN_CANDIDATE.spec_hash "
            f"{frozen.get('spec_hash')}"
        )
    frozen_iter = _normalize_path(Path(str(frozen.get("iter_dir", ""))))
    if frozen_iter != _normalize_path(iter_dir):
        raise ValueError(
            f"iter_dir {iter_dir} != FROZEN_CANDIDATE.iter_dir {frozen.get('iter_dir')}"
        )
    if frozen.get("f5_f6_sealed") is not True:
        raise ValueError("FROZEN_CANDIDATE.f5_f6_sealed must be true")

    bindings = preflight.get("bindings") or {}
    if bindings.get("spec_hash") != freeze_hash:
        raise ValueError("confirm_preflight bindings.spec_hash != freeze_hash")
    approved_base = _normalize_path(Path(str(bindings.get("baseline_iter_dir", ""))))
    if approved_base != _normalize_path(baseline_iter_dir):
        raise ValueError(
            f"baseline_iter_dir {baseline_iter_dir} must match preflight "
            f"{bindings.get('baseline_iter_dir')}"
        )
    approved_iter = _normalize_path(
        Path(str(bindings.get("candidate_iter_dir", "")))
    )
    if approved_iter != _normalize_path(iter_dir):
        raise ValueError(
            f"iter_dir {iter_dir} must match preflight candidate_iter_dir"
        )

    approved_identity = preflight.get("identity") or {}
    drift = identity_snapshot_drift(current_identity, approved_identity)
    if drift:
        raise ValueError(
            "Identity drift from approved confirm_preflight.json: " + "; ".join(drift)
        )
    if approved_identity.get("baseline_spec_hash") != baseline_spec_hash:
        raise ValueError(
            "baseline_spec_hash drift from approved confirm_preflight.json"
        )

    return {
        "frozen_candidate": frozen,
        "confirm_preflight": preflight,
        "approved_identity": approved_identity,
    }


def build_confirm_identity_bundle(
    *,
    feat_path: Path,
    feat_identity: Dict[str, Any],
    iter_dir: Path,
    freeze_hash: str,
    baseline_iter_dir: Path,
    baseline_spec_hash: str,
    candidate_obs_path: Path,
    baseline_obs_path: Path,
) -> Dict[str, Any]:
    codes = gate_code_hashes()
    return {
        "candidate_spec_hash": freeze_hash,
        "feature_parquet_sha256": sha256_file(feat_path),
        "feature_identity": feat_identity,
        "panel_sha256": feat_identity.get("panel_sha256"),
        "folds_yaml_sha256": sha256_file(FOLDS_YAML) if FOLDS_YAML.is_file() else None,
        "folds_version": "1.1",
        "core_sha256": codes["core_sha256"],
        "git": git_identifier(),
        "iter_dir": str(iter_dir),
        "baseline_iter_dir": str(baseline_iter_dir),
        "baseline_spec_hash": baseline_spec_hash,
        "candidate_observations_sha256": observations_parquet_sha256(candidate_obs_path),
        "baseline_observations_sha256": observations_parquet_sha256(baseline_obs_path),
        "confirm_module_sha256": codes["confirm_module_sha256"],
        "score_loop_sha256": codes["score_loop_sha256"],
        "gate_caveat": GATE_POST_HOC_CAVEAT,
        "f6_label": F6_LABEL,
    }


def _prep_obs(obs: pd.DataFrame, horizon: int = 13) -> pd.DataFrame:
    work = obs.copy()
    work["symbol"] = work["symbol"].astype(str).str.upper()
    work["asof"] = pd.to_datetime(work["asof"]).dt.date
    work["score"] = pd.to_numeric(work["score"], errors="coerce")
    ret_col = f"fwd_{horizon}w"
    tgt_col = f"target_date_{horizon}w"
    work[ret_col] = pd.to_numeric(work[ret_col], errors="coerce")
    work[tgt_col] = pd.to_datetime(work[tgt_col], errors="coerce")
    return work


def _fold_frame(
    work: pd.DataFrame,
    folds: Dict[str, Any],
    fold_ids: List[str],
    horizon: int,
) -> pd.DataFrame:
    parts = []
    for fid in fold_ids:
        f = folds[fid]
        part = work[(work["asof"] >= f["oos_start"]) & (work["asof"] <= f["oos_end"])]
        part = filter_outcome_contained(part, horizon, f["oos_end"])
        parts.append(part)
    if not parts:
        return work.iloc[0:0].copy()
    return pd.concat(parts, ignore_index=True)


def _ic_table(
    sub: pd.DataFrame,
    *,
    min_names: int,
    min_per_quintile: int,
    ret_col: str,
) -> pd.DataFrame:
    return date_level_ic_and_spread(
        sub,
        score_col="score",
        ret_col=ret_col,
        min_names=min_names,
        min_per_quintile=min_per_quintile,
    )


def _summarize_ic(
    ic_df: pd.DataFrame,
    *,
    boot_n: int,
    boot_block: int,
    seed: int,
) -> Dict[str, Any]:
    usable = ic_df[ic_df["usable"]] if not ic_df.empty else ic_df
    series = usable["ic"].to_numpy() if not usable.empty else np.array([])
    boot = moving_block_bootstrap_mean(
        series, block_length=boot_block, replicates=boot_n, seed=seed
    )
    return {
        "n_dates": int(len(ic_df)),
        "n_usable_dates": int(usable.shape[0]) if not ic_df.empty else 0,
        "mean_ic": boot["mean"],
        "median_ic": boot["median"],
        "pct_positive": boot["pct_positive"],
        "mean_quintile_spread": (
            float(usable["quintile_spread"].dropna().mean())
            if not usable.empty and usable["quintile_spread"].notna().any()
            else None
        ),
        "bootstrap": boot,
        "eligible_n_min": int(usable["n"].min()) if not usable.empty else None,
        "eligible_n_median": float(usable["n"].median()) if not usable.empty else None,
        "_ic_by_date": {
            str(r["asof"]): float(r["ic"])
            for _, r in usable.iterrows()
            if np.isfinite(r["ic"])
        },
    }


def dual_universe_fold_metrics(
    work: pd.DataFrame,
    folds: Dict[str, Any],
    fold_ids: List[str],
    *,
    spec: Dict[str, Any],
    horizon: int = 13,
) -> Dict[str, Any]:
    eval_cfg = spec["evaluation"]
    min_names = int(eval_cfg.get("min_names_per_date", spec["universe"]["min_symbols"]))
    min_q = int(eval_cfg.get("min_obs_per_quintile", 8))
    boot_n = int((eval_cfg.get("bootstrap") or {}).get("replicates", 10000))
    boot_block = int((eval_cfg.get("bootstrap") or {}).get("block_length_obs", 13))
    seed = int((eval_cfg.get("bootstrap") or {}).get("seed", DEFAULT_BOOTSTRAP_SEED))
    ret_col = f"fwd_{horizon}w"

    frame = _fold_frame(work, folds, fold_ids, horizon)
    ex = frame[~frame["symbol"].isin(EX_VIN)]
    ic_ex = _ic_table(ex, min_names=min_names, min_per_quintile=min_q, ret_col=ret_col)
    ic_full = _ic_table(frame, min_names=min_names, min_per_quintile=min_q, ret_col=ret_col)
    return {
        "ex_vin": _summarize_ic(ic_ex, boot_n=boot_n, boot_block=boot_block, seed=seed),
        "full": _summarize_ic(ic_full, boot_n=boot_n, boot_block=boot_block, seed=seed),
        "fold_ids": list(fold_ids),
        "n_rows_ex_vin": int(len(ex)),
        "n_rows_full": int(len(frame)),
    }


def _eligible_pairs(
    frame: pd.DataFrame,
    *,
    min_names: int,
    ret_col: str,
) -> set[tuple[date, str]]:
    keys: set[tuple[date, str]] = set()
    for asof, g in frame.groupby("asof"):
        sub = g.dropna(subset=["score", ret_col])
        if len(sub) < min_names:
            continue
        for sym in sub["symbol"]:
            keys.add((asof, str(sym)))
    return keys


def audit_paired_coverage(
    candidate_obs: pd.DataFrame,
    baseline_obs: pd.DataFrame,
    folds: Dict[str, Any],
    min_names: int,
    horizon: int = 13,
) -> Dict[str, Any]:
    """Candidate vs CLI must share identical eligible date/symbol cross-sections."""
    cand = _prep_obs(candidate_obs, horizon)
    base = _prep_obs(baseline_obs, horizon)
    ret_col = f"fwd_{horizon}w"
    report: Dict[str, Any] = {"valid": True, "folds": {}, "reasons": []}

    for fid in ("F5", "F6"):
        c_frame = _fold_frame(cand, folds, [fid], horizon)
        b_frame = _fold_frame(base, folds, [fid], horizon)
        fold_report: Dict[str, Any] = {}
        for universe, ex_only in (("ex_vin", True), ("full", False)):
            cf = c_frame[~c_frame["symbol"].isin(EX_VIN)] if ex_only else c_frame
            bf = b_frame[~b_frame["symbol"].isin(EX_VIN)] if ex_only else b_frame
            c_pairs = _eligible_pairs(cf, min_names=min_names, ret_col=ret_col)
            b_pairs = _eligible_pairs(bf, min_names=min_names, ret_col=ret_col)
            c_dates = sorted({d for d, _ in c_pairs})
            b_dates = sorted({d for d, _ in b_pairs})
            block = {
                "candidate_eligible_pairs": len(c_pairs),
                "baseline_eligible_pairs": len(b_pairs),
                "candidate_eligible_dates": len(c_dates),
                "baseline_eligible_dates": len(b_dates),
                "date_set_equal": c_dates == b_dates,
                "pair_set_equal": c_pairs == b_pairs,
                "pairs_only_in_candidate": len(c_pairs - b_pairs),
                "pairs_only_in_baseline": len(b_pairs - c_pairs),
            }
            fold_report[universe] = block
            if not block["date_set_equal"] or not block["pair_set_equal"]:
                report["valid"] = False
                report["reasons"].append(f"{fid}.{universe}: eligibility mismatch")
        fold_report["f6_label"] = F6_LABEL if fid == "F6" else None
        report["folds"][fid] = fold_report
    return report


def paired_ic_delta(
    candidate: Dict[str, Any],
    baseline: Dict[str, Any],
    *,
    universe: str,
    boot_n: int,
    boot_block: int,
    seed: int,
    require_identical_usable_dates: bool = True,
) -> Dict[str, Any]:
    """Per-Friday IC delta (candidate - CLI) for ex_vin or full universe."""
    c_map = (candidate.get(universe) or {}).get("_ic_by_date") or {}
    b_map = (baseline.get(universe) or {}).get("_ic_by_date") or {}
    c_dates = set(c_map)
    b_dates = set(b_map)
    coverage_mismatch = False
    if require_identical_usable_dates and c_dates != b_dates:
        coverage_mismatch = True
        shared: List[str] = []
        deltas = np.array([], dtype=float)
    else:
        shared = sorted(c_dates & b_dates)
        deltas = np.array([c_map[d] - b_map[d] for d in shared], dtype=float)

    if len(deltas) == 0:
        boot = {
            "mean": None,
            "median": None,
            "pct_positive": None,
            "bootstrap_mean_ci95_low": None,
        }
    else:
        boot = moving_block_bootstrap_mean(
            deltas, block_length=boot_block, replicates=boot_n, seed=seed
        )

    return {
        "universe": universe,
        "n_shared_dates": int(len(shared)),
        "candidate_usable_dates": int(len(c_dates)),
        "baseline_usable_dates": int(len(b_dates)),
        "coverage_mismatch": coverage_mismatch,
        "mean_delta": boot["mean"],
        "median_delta": boot["median"],
        "pct_positive_delta": boot["pct_positive"],
        "bootstrap": boot,
    }


def paired_exvin_delta(
    candidate: Dict[str, Any],
    baseline: Dict[str, Any],
    *,
    boot_n: int,
    boot_block: int,
    seed: int,
    require_identical_usable_dates: bool = True,
) -> Dict[str, Any]:
    """Per-Friday IC delta (candidate - CLI) on ex-VIN usable dates."""
    return paired_ic_delta(
        candidate,
        baseline,
        universe="ex_vin",
        boot_n=boot_n,
        boot_block=boot_block,
        seed=seed,
        require_identical_usable_dates=require_identical_usable_dates,
    )


def strip_internal_ic_maps(node: Any) -> Any:
    """Remove _ic_by_date before writing artifacts (keeps payload lean)."""
    if isinstance(node, dict):
        return {
            k: strip_internal_ic_maps(v)
            for k, v in node.items()
            if k != "_ic_by_date"
        }
    if isinstance(node, list):
        return [strip_internal_ic_maps(x) for x in node]
    return node


def classify_confirmation_readout(artifact: Dict[str, Any]) -> str:
    """Predeclared readout classes (ChatGPT Confirm Decision § blocking #4)."""
    if artifact.get("identity_invalid") or artifact.get("coverage_invalid"):
        return "INVALID"

    folds = artifact.get("folds") or {}
    for fid in ("F5", "F6"):
        block = folds.get(fid) or {}
        ex = (block.get("candidate") or {}).get("ex_vin") or {}
        full = (block.get("candidate") or {}).get("full") or {}
        mean_ex = ex.get("mean_ic")
        mean_full = full.get("mean_ic")
        if mean_ex is None or not np.isfinite(mean_ex) or mean_ex <= 0:
            return "FAIL"
        if mean_full is None or not np.isfinite(mean_full):
            return "FAIL"
        if (mean_ex > 0) != (mean_full > 0):
            return "FAIL"

    combined = artifact.get("combined_F5_F6") or {}
    delta = combined.get("paired_exvin_delta") or {}
    mean_delta = delta.get("mean_delta")
    if mean_delta is None or not np.isfinite(mean_delta) or mean_delta <= 0:
        return "FAIL"

    ci_lo = (delta.get("bootstrap") or {}).get("bootstrap_mean_ci95_low")
    if ci_lo is not None and np.isfinite(ci_lo) and ci_lo > 0:
        return "RESEARCH_CONFIRM_PASS"
    return "DIRECTIONAL_PASS_INCONCLUSIVE"


def assert_confirm_bindings(
    *,
    spec: Dict[str, Any],
    spec_path: Path,
    iter_dir: Path,
    freeze_hash: str,
) -> Tuple[str, Dict[str, Any]]:
    """Verify hash matches supplied spec and iter_dir/spec.json."""
    h_supplied = spec_hash(spec)
    if h_supplied != freeze_hash:
        raise ValueError(
            f"spec-hash mismatch: arg={freeze_hash} supplied_spec={h_supplied}"
        )
    iter_spec_path = iter_dir / "spec.json"
    if not iter_spec_path.exists():
        raise FileNotFoundError(f"Missing {iter_spec_path}")
    iter_spec = json.loads(iter_spec_path.read_text(encoding="utf-8"))
    h_iter = spec_hash(iter_spec)
    if h_iter != freeze_hash:
        raise ValueError(
            f"iter_dir/spec.json hash {h_iter} != frozen {freeze_hash}"
        )
    # Path existence check for the canonical freeze file is caller's job.
    return h_supplied, {
        "spec_path": str(spec_path),
        "iter_spec_path": str(iter_spec_path),
        "spec_hash": h_supplied,
        "iter_spec_hash": h_iter,
    }


def build_confirmation_artifact(
    *,
    candidate_obs: pd.DataFrame,
    baseline_obs: pd.DataFrame,
    candidate_spec: Dict[str, Any],
    baseline_spec: Dict[str, Any],
    folds: Dict[str, Any],
    identity: Dict[str, Any],
    identity_invalid: bool = False,
) -> Dict[str, Any]:
    """Full confirmation payload. Caller must not write until authorized."""
    horizon = 13
    cand = _prep_obs(candidate_obs, horizon)
    base = _prep_obs(baseline_obs, horizon)
    eval_cfg = candidate_spec["evaluation"]
    min_names = int(
        eval_cfg.get("min_names_per_date", candidate_spec["universe"]["min_symbols"])
    )
    boot_n = int((eval_cfg.get("bootstrap") or {}).get("replicates", 10000))
    boot_block = int((eval_cfg.get("bootstrap") or {}).get("block_length_obs", 13))
    seed = int((eval_cfg.get("bootstrap") or {}).get("seed", DEFAULT_BOOTSTRAP_SEED))

    coverage = audit_paired_coverage(
        candidate_obs=cand,
        baseline_obs=base,
        folds=folds,
        min_names=min_names,
        horizon=horizon,
    )
    coverage_invalid = not coverage.get("valid", False)

    def _paired_both(
        c_metrics: Dict[str, Any], b_metrics: Dict[str, Any]
    ) -> Dict[str, Any]:
        return {
            "paired_exvin_delta": paired_ic_delta(
                c_metrics,
                b_metrics,
                universe="ex_vin",
                boot_n=boot_n,
                boot_block=boot_block,
                seed=seed,
                require_identical_usable_dates=True,
            ),
            "paired_full_delta": paired_ic_delta(
                c_metrics,
                b_metrics,
                universe="full",
                boot_n=boot_n,
                boot_block=boot_block,
                seed=seed,
                require_identical_usable_dates=True,
            ),
        }

    fold_out: Dict[str, Any] = {}
    for fid in ("F5", "F6"):
        c = dual_universe_fold_metrics(cand, folds, [fid], spec=candidate_spec)
        b = dual_universe_fold_metrics(base, folds, [fid], spec=baseline_spec)
        paired = _paired_both(c, b)
        fold_out[fid] = {
            "sealed_opened": True,
            "f6_label": F6_LABEL if fid == "F6" else None,
            "candidate": c,
            "cli_baseline": b,
            **paired,
        }

    c_both = dual_universe_fold_metrics(
        cand, folds, ["F5", "F6"], spec=candidate_spec
    )
    b_both = dual_universe_fold_metrics(
        base, folds, ["F5", "F6"], spec=baseline_spec
    )
    paired_both = _paired_both(c_both, b_both)
    delta_both = paired_both["paired_exvin_delta"]

    artifact: Dict[str, Any] = {
        "schema_version": "2.1_confirm",
        "label": "RESEARCH_ONLY_NOT_PRODUCTION",
        "metric_role": "confirmation",
        "primary_metric": "mean_date_level_exvin_spearman_ic_13w",
        "selection_primary": "ex_vin",
        "gate_caveat": GATE_POST_HOC_CAVEAT,
        "stop_rule_note": (
            "protocol stop=2 consecutive non-improvements; "
            "loop continued through 5 probes after iter_05 (winner unchanged)"
        ),
        "identity": identity,
        "identity_invalid": identity_invalid,
        "coverage_invalid": coverage_invalid,
        "coverage_audit": coverage,
        "folds": fold_out,
        "combined_F5_F6": {
            "candidate": c_both,
            "cli_baseline": b_both,
            "paired_exvin_delta": paired_both["paired_exvin_delta"],
            "paired_full_delta": paired_both["paired_full_delta"],
            "f6_label": F6_LABEL,
        },
        # Confirmation primary = combined ex-VIN candidate (NOT F1-F4 development).
        "primary": c_both["ex_vin"],
        "primary_scope": "combined_F5_F6_ex_vin",
        "cli_baseline_primary": b_both["ex_vin"],
        "paired_exvin_delta_primary": delta_both,
        "paired_full_delta_primary": paired_both["paired_full_delta"],
    }
    artifact["readout"] = classify_confirmation_readout(artifact)
    return strip_internal_ic_maps(artifact)


def confirm_preflight_counts(
    *,
    candidate_obs: pd.DataFrame,
    baseline_obs: pd.DataFrame,
    folds: Dict[str, Any],
    min_names: int,
) -> Dict[str, Any]:
    """Metrics-suppressed: dates/rows + coverage parity — never mean_ic."""
    horizon = 13
    cand = _prep_obs(candidate_obs, horizon)
    base = _prep_obs(baseline_obs, horizon)
    coverage = audit_paired_coverage(
        candidate_obs=cand,
        baseline_obs=base,
        folds=folds,
        min_names=min_names,
        horizon=horizon,
    )
    out: Dict[str, Any] = {
        "min_names": min_names,
        "coverage_parity": coverage,
        "folds": {},
    }
    for fid in ("F5", "F6"):
        f = folds[fid]
        c = _fold_frame(cand, folds, [fid], horizon)
        b = _fold_frame(base, folds, [fid], horizon)
        c_ex = c[~c["symbol"].isin(EX_VIN)]
        b_ex = b[~b["symbol"].isin(EX_VIN)]
        c_dates = sorted({d for d in c_ex["asof"].unique()})
        b_dates = sorted({d for d in b_ex["asof"].unique()})
        ret = "fwd_13w"

        def _eligible_dates(df: pd.DataFrame) -> int:
            n_ok = 0
            for _, g in df.groupby("asof"):
                sub = g.dropna(subset=["score", ret])
                if len(sub) >= min_names:
                    n_ok += 1
            return n_ok

        out["folds"][fid] = {
            "oos_start": str(f["oos_start"]),
            "oos_end": str(f["oos_end"]),
            "candidate_rows_ex_vin": int(len(c_ex)),
            "baseline_rows_ex_vin": int(len(b_ex)),
            "candidate_asof_n": int(len(c_dates)),
            "baseline_asof_n": int(len(b_dates)),
            "candidate_eligible_dates_ge_min_names": _eligible_dates(c_ex),
            "baseline_eligible_dates_ge_min_names": _eligible_dates(b_ex),
            "f6_label": F6_LABEL if fid == "F6" else None,
            "ic_computed": False,
            "coverage_parity": coverage["folds"].get(fid),
        }
    out["ic_computed"] = False
    out["f5_f6_still_sealed_until_authorized_confirm"] = True
    return out
