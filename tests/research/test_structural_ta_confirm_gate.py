"""Confirmation-gate tests (synthetic data only — never load real F5/F6 IC)."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from scripts.research.structural_ta_predictive_confirm import (
    CONFIRM_LOCK_NAME,
    CONFIRMATION_METRICS_NAME,
    CONFIRMATION_RECEIPT_NAME,
    CONFIRMATION_SPENT_NAME,
    CONFIRM_PREFLIGHT_NAME,
    F6_LABEL,
    assert_approved_preflight_hash,
    assert_confirm_bindings,
    audit_paired_coverage,
    build_confirm_identity_bundle,
    build_confirmation_artifact,
    claim_confirmation_slot,
    classify_confirmation_readout,
    confirm_preflight_counts,
    confirm_preflight_file_sha256,
    enforce_approved_snapshot,
    finalize_confirmation_bundle,
    gate_code_hashes,
    identity_snapshot_drift,
    mark_confirmation_spent,
    paired_exvin_delta,
    paired_ic_delta,
    strip_internal_ic_maps,
    write_confirmation_bundle,
)
from scripts.research.structural_ta_predictive_core import sha256_file, load_canonical_folds, spec_hash
from scripts.research import structural_ta_predictive_score_loop as loop

REPO = Path(__file__).resolve().parents[2]
SPEC05 = REPO / "data" / "research" / "structural_ta_predictive" / "spec_iter_05.json"
ITER05 = REPO / "data" / "research" / "structural_ta_predictive" / "iter_05"
OUT = REPO / "data" / "research" / "structural_ta_predictive"
ITER00 = OUT / "iter_00"
HASH05 = "12c104d7c883269490a500f1b44676dfa466679ab6a2aff1f3b79876b0fa2481"
# v3 gate code — regenerate preflight when confirm/score_loop changes.
REVIEWED_PREFLIGHT_SHA = (
    "28822bf2e14aea82bb0109ad27c82e9b4302960e84a752682d791597fa720c43"
)
STALE_V2_CONFIRM_MODULE_SHA = (
    "fc37e37b000000000000000000000000000000000000000000000000000000005ee2"
)


def _mini_spec() -> dict:
    spec = json.loads(SPEC05.read_text(encoding="utf-8"))
    spec["evaluation"]["bootstrap"]["replicates"] = 50
    spec["evaluation"]["min_names_per_date"] = 5
    spec["evaluation"]["min_obs_per_quintile"] = 1
    return spec


def _synth_obs(asofs: list[date], score_scale: float = 1.0) -> pd.DataFrame:
    names = ["AAA", "BBB", "CCC", "DDD", "EEE", "VIC"]
    rows = []
    for d in asofs:
        for i, s in enumerate(names):
            rows.append(
                {
                    "symbol": s,
                    "asof": d,
                    "score": float(i) * score_scale,
                    "fwd_13w": float(i) * 0.01 * score_scale,
                    "target_date_13w": date(d.year, min(d.month + 3, 12), 15),
                }
            )
    return pd.DataFrame(rows)


def _write_preflight_snapshot(
    iter_dir: Path,
    out_dir: Path,
    base_dir: Path,
    identity: dict,
) -> str:
    body = {
        "schema_version": "2.2_confirm_preflight",
        "bindings": {
            "spec_hash": HASH05,
            "baseline_iter_dir": str(base_dir),
            "candidate_iter_dir": str(iter_dir),
        },
        "identity": identity,
    }
    path = iter_dir / CONFIRM_PREFLIGHT_NAME
    path.write_text(json.dumps(body, indent=2), encoding="utf-8")
    return sha256_file(path)


def test_classify_invalid_flags() -> None:
    assert classify_confirmation_readout({"identity_invalid": True}) == "INVALID"
    assert classify_confirmation_readout({"coverage_invalid": True}) == "INVALID"


def test_build_confirmation_artifact_paired_deltas() -> None:
    spec = _mini_spec()
    folds = load_canonical_folds(date(2026, 8, 27))
    f5_dates = [date(2023, 6, 2), date(2023, 6, 9), date(2023, 6, 16)]
    f6_dates = [date(2025, 6, 6), date(2025, 6, 13), date(2025, 6, 20)]
    cand = _synth_obs(f5_dates + f6_dates, score_scale=1.0)
    base = _synth_obs(f5_dates + f6_dates, score_scale=0.5)
    base = base.copy()
    base.loc[base["symbol"] != "VIC", "score"] = (
        4.0 - base.loc[base["symbol"] != "VIC", "score"]
    )
    art = build_confirmation_artifact(
        candidate_obs=cand,
        baseline_obs=base,
        candidate_spec=spec,
        baseline_spec=spec,
        folds=folds,
        identity={"test": True},
    )
    assert "paired_full_delta" in art["combined_F5_F6"]
    assert "paired_full_delta_primary" in art


def test_coverage_mismatch_yields_invalid() -> None:
    spec = _mini_spec()
    folds = load_canonical_folds(date(2026, 8, 27))
    f5 = [date(2023, 6, 2), date(2023, 6, 9)]
    f6 = [date(2025, 6, 6), date(2025, 6, 13)]
    cand = _synth_obs(f5 + f6)
    base = _synth_obs(f5)
    art = build_confirmation_artifact(
        candidate_obs=cand,
        baseline_obs=base,
        candidate_spec=spec,
        baseline_spec=spec,
        folds=folds,
        identity={"test": True},
    )
    assert art["coverage_invalid"] is True
    assert art["readout"] == "INVALID"


def test_finalize_receipt_binds_metrics_sha256(tmp_path: Path) -> None:
    iter_dir = tmp_path / "iter"
    iter_dir.mkdir()
    lock = claim_confirmation_slot(iter_dir)
    artifact = {"readout": "FAIL", "label": "RESEARCH_ONLY_NOT_PRODUCTION"}
    receipt = {"one_shot": True}
    metrics_path, receipt_path = finalize_confirmation_bundle(
        iter_dir, lock, artifact, receipt
    )
    metrics_sha = sha256_file(metrics_path)
    receipt_data = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt_data["confirmation_metrics_sha256"] == metrics_sha
    assert not (iter_dir / CONFIRM_LOCK_NAME).exists()


def test_mark_spent_forbids_retry(tmp_path: Path) -> None:
    iter_dir = tmp_path / "iter_spent"
    iter_dir.mkdir()
    lock = claim_confirmation_slot(iter_dir)
    spent = mark_confirmation_spent(
        iter_dir,
        lock,
        reason="synthetic failure",
        approved_preflight_sha256="abc",
    )
    assert spent.exists()
    assert (iter_dir / CONFIRMATION_SPENT_NAME).exists()
    with pytest.raises(FileExistsError, match="SPENT"):
        claim_confirmation_slot(iter_dir)


def test_write_bundle_failure_leaves_spent(tmp_path: Path) -> None:
    iter_dir = tmp_path / "iter_fail"
    iter_dir.mkdir()
    artifact = {"readout": "FAIL"}
    receipt = {"approved_preflight_sha256": "x"}

    def _boom(*_a, **_k):
        raise RuntimeError("receipt write failed")

    import scripts.research.structural_ta_predictive_confirm as confirm_mod

    orig = confirm_mod.finalize_confirmation_bundle
    confirm_mod.finalize_confirmation_bundle = _boom
    try:
        with pytest.raises(RuntimeError, match="receipt write failed"):
            write_confirmation_bundle(iter_dir, artifact, receipt)
    finally:
        confirm_mod.finalize_confirmation_bundle = orig

    assert (iter_dir / CONFIRMATION_SPENT_NAME).exists()
    assert not (iter_dir / CONFIRMATION_METRICS_NAME).exists()
    with pytest.raises(FileExistsError, match="SPENT"):
        claim_confirmation_slot(iter_dir)


def test_assert_approved_preflight_hash_mismatch(tmp_path: Path) -> None:
    iter_dir = tmp_path / "iter_pf"
    iter_dir.mkdir()
    (iter_dir / CONFIRM_PREFLIGHT_NAME).write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="approved-preflight-sha256 mismatch"):
        assert_approved_preflight_hash(iter_dir, "deadbeef")


def test_preflight_gate_hashes_match_current_v3_code() -> None:
    if not (ITER05 / CONFIRM_PREFLIGHT_NAME).exists():
        pytest.skip("research preflight not present")
    preflight = json.loads((ITER05 / CONFIRM_PREFLIGHT_NAME).read_text(encoding="utf-8"))
    embedded = preflight["identity"]
    codes = gate_code_hashes()
    assert embedded["confirm_module_sha256"] == codes["confirm_module_sha256"]
    assert embedded["score_loop_sha256"] == codes["score_loop_sha256"]


def test_preflight_identity_matches_live_v3_bundle() -> None:
    """Regression: embedded identity must match live build_confirm_identity_bundle."""
    if not (ITER05 / CONFIRM_PREFLIGHT_NAME).exists():
        pytest.skip("research preflight not present")
    spec = json.loads(SPEC05.read_text(encoding="utf-8"))
    baseline_spec = json.loads((ITER00 / "spec.json").read_text(encoding="utf-8"))
    preflight = json.loads((ITER05 / CONFIRM_PREFLIGHT_NAME).read_text(encoding="utf-8"))
    embedded = preflight["identity"]
    feat_path = OUT / "features" / "features_panel.parquet"
    feat_identity = json.loads(
        (OUT / "features" / "identity.json").read_text(encoding="utf-8")
    )
    live = build_confirm_identity_bundle(
        feat_path=feat_path,
        feat_identity=feat_identity,
        iter_dir=ITER05,
        freeze_hash=HASH05,
        baseline_iter_dir=ITER00,
        baseline_spec_hash=spec_hash(baseline_spec),
        candidate_obs_path=ITER05 / "observations.parquet",
        baseline_obs_path=ITER00 / "observations.parquet",
    )
    drift = identity_snapshot_drift(live, embedded)
    assert drift == [], f"stale preflight identity vs v3 code: {drift}"


def test_preflight_file_sha_is_current() -> None:
    if not (ITER05 / CONFIRM_PREFLIGHT_NAME).exists():
        pytest.skip("research preflight not present")
    assert confirm_preflight_file_sha256(ITER05) == REVIEWED_PREFLIGHT_SHA


def test_stale_embedded_gate_identity_fails_enforce(tmp_path: Path) -> None:
    out_dir = tmp_path / "research"
    iter_dir = out_dir / "iter_05"
    base_dir = out_dir / "iter_00"
    iter_dir.mkdir(parents=True)
    base_dir.mkdir()
    spec = json.loads(SPEC05.read_text(encoding="utf-8"))
    current = {
        "candidate_spec_hash": HASH05,
        "baseline_spec_hash": spec_hash(spec),
        "confirm_module_sha256": gate_code_hashes()["confirm_module_sha256"],
        "score_loop_sha256": gate_code_hashes()["score_loop_sha256"],
        "git": "live",
    }
    stale = dict(current)
    stale["confirm_module_sha256"] = STALE_V2_CONFIRM_MODULE_SHA
    pf_sha = _write_preflight_snapshot(iter_dir, out_dir, base_dir, stale)
    (out_dir / "FROZEN_CANDIDATE.json").write_text(
        json.dumps(
            {
                "spec_hash": HASH05,
                "iter_dir": str(iter_dir),
                "f5_f6_sealed": True,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Identity drift"):
        enforce_approved_snapshot(
            out_dir=out_dir,
            iter_dir=iter_dir,
            freeze_hash=HASH05,
            baseline_iter_dir=base_dir,
            baseline_spec_hash=spec_hash(spec),
            current_identity=current,
            approved_preflight_sha256=pf_sha,
        )


def test_enforce_approved_snapshot_baseline_mismatch(tmp_path: Path) -> None:
    out_dir = tmp_path / "research"
    iter_dir = out_dir / "iter_05"
    base_dir = out_dir / "iter_00"
    wrong_base = out_dir / "iter_01"
    iter_dir.mkdir(parents=True)
    base_dir.mkdir()
    wrong_base.mkdir()
    identity = {"candidate_spec_hash": HASH05, "baseline_spec_hash": "abc"}
    pf_sha = _write_preflight_snapshot(iter_dir, out_dir, base_dir, identity)
    (out_dir / "FROZEN_CANDIDATE.json").write_text(
        json.dumps(
            {
                "spec_hash": HASH05,
                "iter_dir": str(iter_dir),
                "f5_f6_sealed": True,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="baseline_iter_dir"):
        enforce_approved_snapshot(
            out_dir=out_dir,
            iter_dir=iter_dir,
            freeze_hash=HASH05,
            baseline_iter_dir=wrong_base,
            baseline_spec_hash="abc",
            current_identity=identity,
            approved_preflight_sha256=pf_sha,
        )


def test_cmd_confirm_claim_before_ic(tmp_path: Path, monkeypatch) -> None:
    out_dir = tmp_path / "research"
    iter_dir = out_dir / "iter_05"
    base_dir = out_dir / "iter_00"
    iter_dir.mkdir(parents=True)
    base_dir.mkdir(parents=True)
    feat_dir = out_dir / "features"
    feat_dir.mkdir()
    (feat_dir / "features_panel.parquet").write_bytes(b"feat")
    (feat_dir / "identity.json").write_text(
        json.dumps({"panel_sha256": "p", "core_sha256": "c"}),
        encoding="utf-8",
    )
    spec = json.loads(SPEC05.read_text(encoding="utf-8"))
    (iter_dir / "spec.json").write_text(json.dumps(spec), encoding="utf-8")
    (base_dir / "spec.json").write_text(json.dumps(spec), encoding="utf-8")
    f5 = [date(2023, 6, 2)]
    f6 = [date(2025, 6, 6)]
    obs = _synth_obs(f5 + f6)
    obs.to_parquet(iter_dir / "observations.parquet", index=False)
    obs.to_parquet(base_dir / "observations.parquet", index=False)
    identity = {
        "candidate_spec_hash": HASH05,
        "baseline_spec_hash": spec_hash(spec),
        "feature_parquet_sha256": sha256_file(feat_dir / "features_panel.parquet"),
        "panel_sha256": "p",
        "folds_yaml_sha256": "f",
        "folds_version": "1.1",
        "core_sha256": "c",
        "git": "g",
        "iter_dir": str(iter_dir),
        "baseline_iter_dir": str(base_dir),
        "candidate_observations_sha256": sha256_file(iter_dir / "observations.parquet"),
        "baseline_observations_sha256": sha256_file(base_dir / "observations.parquet"),
        "confirm_module_sha256": "cm",
        "score_loop_sha256": "sl",
    }
    pf_sha = _write_preflight_snapshot(iter_dir, out_dir, base_dir, identity)
    (out_dir / "FROZEN_CANDIDATE.json").write_text(
        json.dumps(
            {
                "spec_hash": HASH05,
                "iter_dir": str(iter_dir),
                "f5_f6_sealed": True,
            }
        ),
        encoding="utf-8",
    )

    order: list[str] = []

    def _track_claim(iter_dir_arg: Path) -> Path:
        order.append("claim")
        return claim_confirmation_slot(iter_dir_arg)

    monkeypatch.setattr(
        "scripts.research.structural_ta_predictive_score_loop.claim_confirmation_slot",
        _track_claim,
    )
    def _track_ic(**_kw) -> dict:
        order.append("ic")
        assert (iter_dir / CONFIRM_LOCK_NAME).exists(), "lock must exist before IC"
        return {
            "readout": "FAIL",
            "primary": {"mean_ic": 0.01},
            "primary_scope": "combined_F5_F6_ex_vin",
            "paired_exvin_delta_primary": {"mean_delta": 0.01},
            "paired_full_delta_primary": {"mean_delta": 0.01},
        }

    monkeypatch.setattr(loop, "build_confirmation_artifact", _track_ic)
    monkeypatch.setattr(
        loop,
        "build_confirm_identity_bundle",
        lambda **kw: identity,
    )

    loop.cmd_confirm(
        SPEC05,
        iter_dir,
        HASH05,
        base_dir,
        out_dir,
        authorize_chatgpt_reclear=True,
        approved_preflight_sha256=pf_sha,
    )
    assert order == ["claim", "ic"]
    receipt = json.loads((iter_dir / CONFIRMATION_RECEIPT_NAME).read_text(encoding="utf-8"))
    assert receipt.get("confirmation_metrics_sha256")


def test_cmd_confirm_failure_after_claim_writes_spent(tmp_path: Path, monkeypatch) -> None:
    out_dir = tmp_path / "research"
    iter_dir = out_dir / "iter_05"
    base_dir = out_dir / "iter_00"
    iter_dir.mkdir(parents=True)
    base_dir.mkdir(parents=True)
    feat_dir = out_dir / "features"
    feat_dir.mkdir()
    (feat_dir / "features_panel.parquet").write_bytes(b"feat")
    (feat_dir / "identity.json").write_text("{}", encoding="utf-8")
    spec = json.loads(SPEC05.read_text(encoding="utf-8"))
    (iter_dir / "spec.json").write_text(json.dumps(spec), encoding="utf-8")
    (base_dir / "spec.json").write_text(json.dumps(spec), encoding="utf-8")
    obs = _synth_obs([date(2023, 6, 2), date(2025, 6, 6)])
    obs.to_parquet(iter_dir / "observations.parquet", index=False)
    obs.to_parquet(base_dir / "observations.parquet", index=False)
    identity = {
        "candidate_spec_hash": HASH05,
        "baseline_spec_hash": spec_hash(spec),
    }
    pf_sha = _write_preflight_snapshot(iter_dir, out_dir, base_dir, identity)
    (out_dir / "FROZEN_CANDIDATE.json").write_text(
        json.dumps(
            {
                "spec_hash": HASH05,
                "iter_dir": str(iter_dir),
                "f5_f6_sealed": True,
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        loop,
        "build_confirm_identity_bundle",
        lambda **kw: identity,
    )
    monkeypatch.setattr(
        loop,
        "build_confirmation_artifact",
        lambda **kw: {"readout": "FAIL", "primary": {}},
    )

    def _fail_finalize(*_a, **_k):
        raise RuntimeError("finalize failed")

    monkeypatch.setattr(loop, "finalize_confirmation_bundle", _fail_finalize)

    with pytest.raises(RuntimeError, match="finalize failed"):
        loop.cmd_confirm(
            SPEC05,
            iter_dir,
            HASH05,
            base_dir,
            out_dir,
            authorize_chatgpt_reclear=True,
            approved_preflight_sha256=pf_sha,
        )

    assert (iter_dir / CONFIRMATION_SPENT_NAME).exists()
    assert not (iter_dir / CONFIRMATION_METRICS_NAME).exists()
    with pytest.raises(FileExistsError, match="SPENT"):
        claim_confirmation_slot(iter_dir)


def test_confirm_refuses_without_authorize_flag(monkeypatch) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "x",
            "confirm",
            "--spec",
            str(SPEC05),
            "--iter-dir",
            str(ITER05),
            "--spec-hash",
            HASH05,
            "--baseline-iter-dir",
            str(OUT / "iter_00"),
            "--approved-preflight-sha256",
            REVIEWED_PREFLIGHT_SHA,
        ],
    )
    with pytest.raises(SystemExit) as ei:
        loop.main()
    assert "REFUSED" in str(ei.value)


def test_paired_ic_delta_requires_identical_usable_dates() -> None:
    cand = {
        "ex_vin": {
            "_ic_by_date": {"2023-06-02": 0.2, "2023-06-09": 0.1},
            "mean_ic": 0.15,
        },
        "full": {
            "_ic_by_date": {"2023-06-02": 0.2, "2023-06-09": 0.1},
            "mean_ic": 0.15,
        },
    }
    base = {
        "ex_vin": {"_ic_by_date": {"2023-06-02": 0.05}, "mean_ic": 0.05},
        "full": {"_ic_by_date": {"2023-06-02": 0.05}, "mean_ic": 0.05},
    }
    d_ex = paired_ic_delta(cand, base, universe="ex_vin", boot_n=20, boot_block=2, seed=1)
    assert d_ex["coverage_mismatch"] is True
    d_ok = paired_exvin_delta(cand, cand, boot_n=20, boot_block=2, seed=1)
    assert d_ok["n_shared_dates"] == 2
