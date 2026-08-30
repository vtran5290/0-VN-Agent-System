#!/usr/bin/env python3
"""
Structural TA score predictive-value research loop (RESEARCH ONLY).

ChatGPT REDIRECT 2026-08-28. Do not run iteration metrics until preflight
stop-condition passes. Does NOT modify vn_ta_fireant_cli.py or OMS paths.

Commands:
  preflight         — PIT counts, hashes, projected jobs; NO IC
  build-features    — pinned raw bucket panel + labels (checkpointed)
  status            — progress bar (terminal and/or HTML) for build-features
  recompose         — cheap score from frozen features + spec weights
  evaluate          — F1–F4 development date-level IC only (F5/F6 sealed)
  record-freeze     — record frozen candidate hash (F5/F6 stay sealed)
  confirm-preflight — hashes + F5/F6 date/row counts only; NEVER IC
  confirm           — F5/F6 once after ChatGPT re-clear (--authorize-chatgpt-reclear)
"""
from __future__ import annotations

import argparse
import functools
import gc
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import scripts.vn_ta_fireant_cli as cli
from scripts.research.structural_ta_predictive_confirm import (
    CONFIRMATION_METRICS_NAME,
    CONFIRMATION_RECEIPT_NAME,
    CONFIRM_LOCK_NAME,
    CONFIRM_PREFLIGHT_NAME,
    CONFIRMATION_SPENT_NAME,
    FROZEN_CANDIDATE_NAME,
    F6_LABEL,
    GATE_POST_HOC_CAVEAT,
    assert_confirm_bindings,
    build_confirm_identity_bundle,
    build_confirmation_artifact,
    claim_confirmation_slot,
    confirm_preflight_counts,
    enforce_approved_snapshot,
    finalize_confirmation_bundle,
    load_frozen_candidate,
    mark_confirmation_spent,
)
from scripts.research.structural_ta_predictive_core import (
    BUCKET_KEYS,
    CONFIRMATION_FOLDS,
    DEFAULT_BOOTSTRAP_SEED,
    DEVELOPMENT_FOLDS,
    EX_VIN,
    FOLDS_YAML,
    PANEL_PATH,
    VPL,
    assign_confirm_fold,
    assign_dev_fold,
    composite_score,
    contained_in_fold,
    date_level_ic_and_spread,
    daily_count_from_lookup,
    daily_cum_lookup,
    filter_outcome_contained,
    forward_weekly_labels,
    git_identifier,
    identities_match,
    identity_payload,
    is_non_equity_ticker,
    load_canonical_folds,
    moving_block_bootstrap_mean,
    normalize_panel,
    pit_adv50_matrices,
    pit_membership_at_asof,
    sha256_file,
    spec_hash,
    staggered_week_offsets,
    validate_search_space,
    weekly_bars_asof,
    weekly_cum_lookup,
    weekly_count_from_lookup,
    weekly_fridays,
)
from scripts.run_structural_ta_adv50_universe import build_fetch
from scripts.vn_ta_fireant_cli import TAConfig, analyze_ticker

DEFAULT_OUT = REPO_ROOT / "data" / "research" / "structural_ta_predictive"
FEATURES_NAME = "features_panel.parquet"
IDENTITY_NAME = "identity.json"
CHECKPOINT_NAME = "feature_checkpoint.jsonl"
ERROR_LEDGER = "error_ledger.jsonl"
PROGRESS_HTML_NAME = "build_progress.html"
PROGRESS_JSON_NAME = "build_progress.json"


def _count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    count = 0
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            count += chunk.count(b"\n")
    return count


def _projected_jobs(out_dir: Path) -> int:
    pf = out_dir / "preflight.json"
    if pf.exists():
        data = json.loads(pf.read_text(encoding="utf-8"))
        jobs = data.get("projected_analyze_jobs")
        if jobs is not None:
            return int(jobs)
    raise FileNotFoundError(
        f"Missing projected_analyze_jobs in {pf}. Run preflight first."
    )


def _build_progress_snapshot(
    out_dir: Path,
    smoke: bool,
    prev: Optional[Tuple[int, float]] = None,
) -> Dict[str, Any]:
    feat_dir = out_dir / ("features_smoke" if smoke else "features")
    ck_path = feat_dir / CHECKPOINT_NAME
    parquet_path = feat_dir / FEATURES_NAME
    total = _projected_jobs(out_dir)
    done = _count_lines(ck_path)
    now = time.time()
    rate: Optional[float] = None
    if prev is not None and now > prev[1]:
        rate = (done - prev[0]) / (now - prev[1])
    pct = min(100.0, (done / total * 100.0) if total else 0.0)
    remaining = max(total - done, 0)
    eta_sec: Optional[float] = None
    if rate and rate > 0 and remaining > 0:
        eta_sec = remaining / rate
    complete = parquet_path.exists() and done >= total
    return {
        "done": done,
        "total": total,
        "pct": pct,
        "remaining": remaining,
        "rate": rate,
        "eta_sec": eta_sec,
        "complete": complete,
        "checkpoint": str(ck_path),
        "parquet": str(parquet_path),
        "parquet_exists": parquet_path.exists(),
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ts": now,
    }


def _progress_json_payload(snap: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "done": int(snap["done"]),
        "total": int(snap["total"]),
        "pct": round(float(snap["pct"]), 2),
        "remaining": int(snap["remaining"]),
        "rate": round(float(snap["rate"]), 3) if snap.get("rate") else None,
        "eta_sec": round(float(snap["eta_sec"]), 1) if snap.get("eta_sec") else None,
        "complete": bool(snap.get("complete")),
        "updated": snap.get("updated") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def _ensure_progress_html_shell(html_path: Path) -> None:
    html = """<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Structural TA build-features progress</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 2rem; max-width: 720px; color: #111; }
    h1 { font-size: 1.25rem; margin-bottom: 0.25rem; }
    .status { font-size: 0.9rem; color: #444; margin-bottom: 0.5rem; }
    .hint { font-size: 0.85rem; color: #b45309; margin-bottom: 1rem; line-height: 1.4; }
    .bar { height: 28px; background: #e5e7eb; border-radius: 6px; overflow: hidden; border: 1px solid #cbd5e1; }
    .fill { height: 100%; background: #2563eb; width: 0%; transition: width 0.4s ease; }
    .pct { font-size: 1.5rem; font-weight: 600; margin: 0.75rem 0 0.25rem; }
    .meta { font-size: 0.95rem; line-height: 1.6; }
    .label { color: #374151; }
  </style>
</head>
<body>
  <h1>Structural TA — build-features</h1>
  <p class="status">Status: <strong id="status">...</strong> · refresh 5s</p>
  <p class="hint" id="hint"></p>
  <div class="bar" aria-label="progress"><div class="fill" id="fill"></div></div>
  <p class="pct" id="pct">0%</p>
  <p class="meta">
    <span class="label">Jobs:</span> <span id="jobs">...</span>
    (<span id="remaining">...</span> remaining)<br>
    <span class="label">Rate:</span> <span id="rate">...</span><br>
    <span class="label">ETA:</span> <span id="eta">...</span><br>
    <span class="label">Updated:</span> <span id="updated">...</span>
  </p>
  <script>
    function fmtEta(sec) {
      if (!sec) return "unknown";
      const h = Math.floor(sec / 3600);
      const m = Math.floor((sec % 3600) / 60);
      const when = new Date(Date.now() + sec * 1000);
      return h + "h " + m + "m (~" + when.toLocaleTimeString() + ")";
    }
    function apply(d) {
      document.getElementById("fill").style.width = d.pct + "%";
      document.getElementById("pct").textContent = d.pct.toFixed(1) + "%";
      document.getElementById("jobs").textContent =
        d.done.toLocaleString() + " / " + d.total.toLocaleString();
      document.getElementById("remaining").textContent = d.remaining.toLocaleString();
      document.getElementById("rate").textContent =
        d.rate ? d.rate.toFixed(2) + "/s" : "...";
      document.getElementById("eta").textContent = fmtEta(d.eta_sec);
      document.getElementById("updated").textContent = d.updated || "";
      document.getElementById("status").textContent = d.complete ? "COMPLETE" : "RUNNING";
      document.getElementById("hint").textContent = "";
    }
    async function refresh() {
      try {
        const r = await fetch("build_progress.json?t=" + Date.now(), { cache: "no-store" });
        if (!r.ok) throw new Error(String(r.status));
        apply(await r.json());
      } catch (e) {
        document.getElementById("hint").textContent =
          "Mở qua local server (file:// không poll JSON). Chạy: "
          + "python scripts/research/structural_ta_predictive_score_loop.py status "
          + "--watch --serve 8765 --out data/research/structural_ta_predictive "
          + "→ http://127.0.0.1:8765/build_progress.html";
      }
    }
    setInterval(refresh, 5000);
    refresh();
  </script>
</body>
</html>
"""
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(html, encoding="utf-8")


def _publish_progress(feat_dir: Path, snap: Dict[str, Any], html_path: Path) -> None:
    payload = _progress_json_payload(snap)
    json_path = feat_dir / PROGRESS_JSON_NAME
    _json_dump(json_path, payload)
    _ensure_progress_html_shell(html_path)


def _publish_build_progress(
    feat_dir: Path,
    ck_path: Path,
    total: int,
    start_done: int,
    t0: float,
    html_path: Path,
) -> None:
    done_count = _count_lines(ck_path)
    elapsed = max(time.time() - t0, 1e-6)
    session = max(done_count - start_done, 0)
    rate = session / elapsed if session > 0 else None
    remaining = max(total - done_count, 0)
    eta_sec = remaining / rate if rate and rate > 0 and remaining > 0 else None
    pct = min(100.0, (done_count / total * 100.0) if total else 0.0)
    snap = {
        "done": done_count,
        "total": total,
        "pct": pct,
        "remaining": remaining,
        "rate": rate,
        "eta_sec": eta_sec,
        "complete": False,
        "checkpoint": str(ck_path),
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    _publish_progress(feat_dir, snap, html_path)


def _format_eta(eta_sec: Optional[float]) -> str:
    if eta_sec is None:
        return "unknown"
    when = datetime.now() + timedelta(seconds=eta_sec)
    hrs = int(eta_sec // 3600)
    mins = int((eta_sec % 3600) // 60)
    return f"{hrs}h {mins}m (~{when.strftime('%H:%M')})"


def _progress_bar(pct: float, width: int = 40) -> str:
    pct = max(0.0, min(100.0, pct))
    filled = int(round(width * pct / 100.0))
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def _render_progress_line(snap: Dict[str, Any], label: str = "build-features") -> str:
    rate_txt = f"{snap['rate']:.2f}/s" if snap.get("rate") else "measuring..."
    eta_txt = _format_eta(snap.get("eta_sec"))
    if snap.get("complete"):
        return f"{label}  COMPLETE  {snap['done']:,}/{snap['total']:,}"
    bar = _progress_bar(snap["pct"])
    return (
        f"{label}  {bar}  {snap['pct']:.1f}%  "
        f"{snap['done']:,}/{snap['total']:,}  {rate_txt}  ETA {eta_txt}"
    )


def cmd_status(
    out_dir: Path,
    smoke: bool,
    watch: bool,
    interval: float,
    html_path: Optional[Path],
    serve: Optional[int],
) -> None:
    import threading
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

    feat_dir = out_dir / ("features_smoke" if smoke else "features")
    feat_dir.mkdir(parents=True, exist_ok=True)
    default_html = feat_dir / PROGRESS_HTML_NAME
    html_out = html_path or default_html
    _ensure_progress_html_shell(html_out)

    if serve is not None:
        port = int(serve)
        serve_dir = str(feat_dir.resolve())

        def _run_server() -> None:
            handler = functools.partial(SimpleHTTPRequestHandler, directory=serve_dir)
            srv = ThreadingHTTPServer(("127.0.0.1", port), handler)
            srv.serve_forever()

        threading.Thread(target=_run_server, daemon=True).start()
        print(f"Open http://127.0.0.1:{port}/build_progress.html", flush=True)
        print(f"JSON poll -> {feat_dir / PROGRESS_JSON_NAME}", flush=True)

    prev: Optional[Tuple[int, float]] = None
    if watch or serve is not None:
        print("Watching build-features progress (Ctrl+C to stop)", flush=True)

    while True:
        snap = _build_progress_snapshot(out_dir, smoke, prev)
        line = _render_progress_line(snap)
        if watch or serve is not None:
            print("\r" + line + " " * 8, end="", flush=True)
        else:
            print(line, flush=True)
        _publish_progress(feat_dir, snap, html_out)
        if not watch and serve is None:
            print(f"html -> {html_out}", flush=True)
            print(f"json -> {feat_dir / PROGRESS_JSON_NAME}", flush=True)
        if snap.get("complete"):
            if watch or serve is not None:
                print("", flush=True)
            break
        prev = (snap["done"], snap["ts"])
        if not watch and serve is None:
            break
        time.sleep(max(interval, 1.0))


def _load_spec(path: Path) -> Dict[str, Any]:
    spec = json.loads(path.read_text(encoding="utf-8"))
    if spec.get("oos_folds"):
        raise ValueError("spec must not contain inline oos_folds dates; reference walkforward_folds.yaml")
    folds = spec.get("folds") or {}
    if folds.get("version") != "1.1":
        raise ValueError("spec.folds.version must be '1.1'")
    if "F5" in (folds.get("development_ids") or []) or "F6" in (folds.get("development_ids") or []):
        raise ValueError("F5/F6 cannot be development folds")
    validate_search_space(spec)
    return spec


def _json_dump(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str, allow_nan=False), encoding="utf-8")


def _atomic_write_parquet(df: pd.DataFrame, path: Path) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    df.to_parquet(tmp, index=False)
    tmp.replace(path)


def _refuse_overwrite(path: Path, run_id: Optional[str]) -> Path:
    if not path.exists():
        return path
    if not run_id:
        raise FileExistsError(f"Refusing to overwrite {path}. Pass --run-id for a new directory.")
    alt = path.parent / f"{path.name}_{run_id}"
    if alt.exists():
        raise FileExistsError(f"Refusing to overwrite {alt}")
    return alt


def _load_panel() -> tuple[pd.DataFrame, Dict[str, Any], str]:
    if not PANEL_PATH.exists():
        raise FileNotFoundError(f"Missing panel: {PANEL_PATH}")
    raw = pd.read_parquet(PANEL_PATH)
    panel, flags = normalize_panel(raw)
    if "value" not in panel.columns:
        raise ValueError("panel missing `value` column required for PIT ADV50")
    return panel, flags, sha256_file(PANEL_PATH)


def _tier_b_start(spec: Dict[str, Any]) -> date:
    return date.fromisoformat(str(spec["evaluation"]["tier_b_start"]))


def _week_step(spec: Dict[str, Any], smoke: bool) -> int:
    if smoke:
        return 4
    return int(spec["evaluation"].get("week_step", 1))


def _fridays(panel: pd.DataFrame, spec: Dict[str, Any], smoke: bool) -> List[date]:
    start = _tier_b_start(spec)
    end = panel["date"].max().date()
    sessions = panel["date"].drop_duplicates().sort_values()
    return weekly_fridays(sessions, start, end, step=_week_step(spec, smoke))


def _preflight_body(
    spec: Dict[str, Any],
    panel: pd.DataFrame,
    flags: Dict[str, Any],
    panel_sha: str,
    smoke: bool,
) -> Dict[str, Any]:
    u = spec["universe"]
    threshold = float(u["adv50_threshold_vnd"])
    min_sym = int(u["min_symbols"])
    max_sym = int(u["max_symbols"])
    min_bars = int(u["min_weekly_bars"])
    panel_end = panel["date"].max().date()
    folds = load_canonical_folds(panel_end)
    sessions, adv50, active10 = pit_adv50_matrices(panel)
    weekly = weekly_bars_asof(panel)
    week_idx, week_cum = weekly_cum_lookup(weekly)
    day_idx, day_cum = daily_cum_lookup(panel)
    fridays = _fridays(panel, spec, smoke)
    always_exclude = {str(s).upper() for s in u.get("exclude_symbols") or []}

    date_rows = []
    projected = 0
    for asof in fridays:
        memb = pit_membership_at_asof(
            asof, sessions, adv50, active10, threshold=threshold, max_symbols=max_sym
        )
        names = [
            s
            for s in memb.index.astype(str)
            if s not in always_exclude and not is_non_equity_ticker(s)
        ]
        eligible = []
        for sym in names:
            if sym == VPL and daily_count_from_lookup(asof, day_idx, day_cum, VPL) < 252:
                continue
            if weekly_count_from_lookup(asof, week_idx, week_cum, sym) < min_bars:
                continue
            eligible.append(sym)
        n = len(eligible)
        n_exvin = len([s for s in eligible if s not in EX_VIN])
        underpowered = n < min_sym
        dev_fold = assign_dev_fold(asof, folds)
        confirm_fold = assign_confirm_fold(asof, folds)
        if (dev_fold or confirm_fold) and not underpowered:
            projected += n
        date_rows.append(
            {
                "asof": asof.isoformat(),
                "n_pit_liquid": n,
                "n_pit_exvin": n_exvin,
                "underpowered": underpowered,
                "dev_fold": dev_fold,
                "confirm_fold": confirm_fold,
            }
        )

    usable = [r for r in date_rows if r["dev_fold"] and not r["underpowered"]]
    identity = identity_payload(spec=spec, panel_sha256=panel_sha, panel_date_max=panel_end.isoformat())
    return {
        "schema_version": "2.0",
        "label": "RESEARCH_ONLY_NOT_PRODUCTION",
        "diagnostic_not_evidence": bool(smoke),
        "week_step": _week_step(spec, smoke),
        "identity": identity,
        "integrity": flags,
        "n_fridays": len(fridays),
        "n_usable_dates": len(usable),
        "n_underpowered_dates": len(date_rows) - len(usable),
        "projected_analyze_jobs": projected,
        "min_symbols": min_sym,
        "folds_version": "1.1",
        "development_ids": list(DEVELOPMENT_FOLDS),
        "confirmation_ids": sorted(CONFIRMATION_FOLDS),
        "date_rows": date_rows,
        "ic_computed": False,
        "git": git_identifier(),
    }


def cmd_preflight(spec_path: Path, out_dir: Path, smoke: bool) -> Path:
    spec = _load_spec(spec_path)
    panel, flags, panel_sha = _load_panel()
    body = _preflight_body(spec, panel, flags, panel_sha, smoke)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / ("preflight_smoke.json" if smoke else "preflight.json")
    _json_dump(path, body)
    print(f"preflight -> {path} usable_dates={body['n_usable_dates']} jobs={body['projected_analyze_jobs']}")
    return path


_POOL: Dict[str, Any] = {"spec": None, "cfg": None}


def _pool_init(spec: Dict[str, Any]) -> None:
    """Per-process setup: load panel once and pin fetch_ohlcv."""
    panel, _, _ = _load_panel()
    cli.fetch_ohlcv = build_fetch(panel)
    _POOL["spec"] = spec
    _POOL["cfg"] = TAConfig()


def _analyze_into_rec(rec: Dict[str, Any], spec: Dict[str, Any], cfg: TAConfig) -> Dict[str, Any]:
    sym = str(rec["symbol"]).upper()
    asof = date.fromisoformat(str(rec["asof"]))
    try:
        result = analyze_ticker(sym, asof=asof, cfg=cfg)
    except Exception as exc:
        rec["error"] = str(exc)
        rec["score"] = None
        return rec
    ws = result.get("weekly_structure") or {}
    breakdown = ws.get("score_breakdown")
    cli_total = ws.get("structural_support_score")
    rec["cli_total"] = cli_total
    rec["score"] = composite_score(breakdown, spec, cli_total)
    rec["score_unevaluated"] = rec["score"] is None
    if isinstance(breakdown, dict):
        for k in BUCKET_KEYS:
            rec[f"b_{k}"] = breakdown.get(k)
    return rec


def _pool_analyze(rec: Dict[str, Any]) -> Dict[str, Any]:
    return _analyze_into_rec(rec, _POOL["spec"], _POOL["cfg"])


def cmd_build_features(
    spec_path: Path,
    out_dir: Path,
    smoke: bool,
    resume: bool,
    workers: int = 1,
) -> Path:
    spec = _load_spec(spec_path)
    panel, flags, panel_sha = _load_panel()
    identity = identity_payload(
        spec=spec,
        panel_sha256=panel_sha,
        panel_date_max=panel["date"].max().date().isoformat(),
        extra={"integrity": flags, "smoke": smoke},
    )
    feat_dir = out_dir / ("features_smoke" if smoke else "features")
    feat_dir.mkdir(parents=True, exist_ok=True)
    id_path = feat_dir / IDENTITY_NAME
    if id_path.exists():
        prev = json.loads(id_path.read_text(encoding="utf-8"))
        if not identities_match(prev, identity, ["panel_sha256", "folds_yaml_sha256", "core_sha256"]):
            raise RuntimeError("Checkpoint identity mismatch — refuse resume. Rebuild with --run-id.")
        if not resume:
            raise FileExistsError(f"{id_path} exists. Pass --resume or --run-id.")
    else:
        _json_dump(id_path, identity)

    u = spec["universe"]
    eval_cfg = spec["evaluation"]
    horizons = [int(h) for h in eval_cfg["horizons_weeks"]]
    sessions, adv50, active10 = pit_adv50_matrices(panel)
    weekly = weekly_bars_asof(panel)
    week_idx, week_cum = weekly_cum_lookup(weekly)
    day_idx, day_cum = daily_cum_lookup(panel)
    labels = forward_weekly_labels(weekly, horizons)

    def _asof_key(v: Any) -> str:
        return pd.Timestamp(v).date().isoformat()

    label_ix = {
        (str(r["symbol"]).upper(), _asof_key(r["asof"])): r
        for r in labels.to_dict("records")
    }
    fridays = _fridays(panel, spec, smoke)
    folds = load_canonical_folds(panel["date"].max().date())

    done: set[tuple[str, str]] = set()
    ck_path = feat_dir / CHECKPOINT_NAME
    # Resume: keys only — full records rebuilt from checkpoint at the end (saves RAM).
    if resume and ck_path.exists():
        with ck_path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                done.add((rec["symbol"], rec["asof"]))

    workers = max(1, int(workers))
    cfg = TAConfig()
    err_path = feat_dir / ERROR_LEDGER
    min_bars = int(u["min_weekly_bars"])
    threshold = float(u["adv50_threshold_vnd"])
    max_sym = int(u["max_symbols"])
    min_sym = int(u["min_symbols"])
    always_exclude = {str(s).upper() for s in u.get("exclude_symbols") or []}

    pending: List[Dict[str, Any]] = []
    for asof in fridays:
        if assign_dev_fold(asof, folds) is None and assign_confirm_fold(asof, folds) is None:
            continue
        memb = pit_membership_at_asof(
            asof, sessions, adv50, active10, threshold=threshold, max_symbols=max_sym
        )
        names = [
            s
            for s in memb.index.astype(str)
            if s not in always_exclude and not is_non_equity_ticker(s)
        ]
        eligible_syms = []
        for sym in names:
            d_bars = daily_count_from_lookup(asof, day_idx, day_cum, sym)
            w_bars = weekly_count_from_lookup(asof, week_idx, week_cum, sym)
            if sym == VPL and d_bars < 252:
                continue
            if w_bars < min_bars:
                continue
            eligible_syms.append(sym)
        if len(eligible_syms) < min_sym:
            continue
        for sym in eligible_syms:
            key = (sym, asof.isoformat())
            if key in done:
                continue
            lab = label_ix.get((sym, asof.isoformat()), {})
            rec: Dict[str, Any] = {
                "symbol": sym,
                "asof": asof.isoformat(),
                "pit_adv50": (
                    None
                    if pd.isna(memb.get(sym, float("nan")))
                    else float(memb.get(sym))
                ),
                "weekly_bars_asof": weekly_count_from_lookup(asof, week_idx, week_cum, sym),
                "daily_bars_asof": daily_count_from_lookup(asof, day_idx, day_cum, sym),
                "dev_fold": assign_dev_fold(asof, folds),
                "confirm_fold": assign_confirm_fold(asof, folds),
                "cli_total": None,
                "score_unevaluated": True,
            }
            for h in horizons:
                rec[f"fwd_{h}w"] = lab.get(f"fwd_{h}w")
                td = lab.get(f"target_date_{h}w")
                rec[f"target_date_{h}w"] = (
                    td.isoformat() if isinstance(td, date) else (str(td) if td else None)
                )
            pending.append(rec)

    if workers == 1:
        cli.fetch_ohlcv = build_fetch(panel)
    else:
        # Free parent panel before ProcessPool so peak ≈ workers×panel (not 3×).
        del panel, sessions, adv50, active10, weekly, week_idx, week_cum
        del day_idx, day_cum, labels, label_ix, fridays, folds
        gc.collect()
        print(
            f"build-features: freed parent panel before ProcessPool (workers={workers})",
            flush=True,
        )

    t0 = time.time()
    total_jobs = _projected_jobs(out_dir)
    start_done = _count_lines(ck_path)
    progress_html = feat_dir / PROGRESS_HTML_NAME
    _ensure_progress_html_shell(progress_html)
    _publish_build_progress(feat_dir, ck_path, total_jobs, start_done, t0, progress_html)
    print(
        f"build-features: analyze_ticker loop  pending={len(pending)} workers={workers}",
        flush=True,
    )

    def _commit(rec: Dict[str, Any], jobs_done: int) -> int:
        if rec.get("error"):
            with err_path.open("a", encoding="utf-8") as ef:
                ef.write(
                    json.dumps(
                        {"symbol": rec["symbol"], "asof": rec["asof"], "error": rec["error"]}
                    )
                    + "\n"
                )
        with ck_path.open("a", encoding="utf-8") as cf:
            cf.write(json.dumps(rec, default=str) + "\n")
        jobs_done += 1
        if jobs_done % 50 == 0:
            elapsed = max(time.time() - t0, 1e-6)
            rate = jobs_done / elapsed
            print(
                f"  features {jobs_done} new rows  {rate:.2f}/s  "
                f"elapsed_min={elapsed/60:.1f}  workers={workers}",
                flush=True,
            )
            _publish_build_progress(
                feat_dir, ck_path, total_jobs, start_done, t0, progress_html
            )
        return jobs_done

    jobs = 0
    if workers == 1:
        for rec in pending:
            jobs = _commit(_analyze_into_rec(rec, spec, cfg), jobs)
    else:
        max_inflight = max(workers * 4, workers)
        with ProcessPoolExecutor(
            max_workers=workers,
            initializer=_pool_init,
            initargs=(spec,),
        ) as pool:
            it = iter(pending)
            inflight: Dict[Any, None] = {}

            def _submit_one() -> bool:
                try:
                    nxt = next(it)
                except StopIteration:
                    return False
                inflight[pool.submit(_pool_analyze, nxt)] = None
                return True

            for _ in range(min(max_inflight, len(pending))):
                if not _submit_one():
                    break
            while inflight:
                fut = next(as_completed(inflight))
                del inflight[fut]
                jobs = _commit(fut.result(), jobs)
                _submit_one()

    _publish_build_progress(feat_dir, ck_path, total_jobs, start_done, t0, progress_html)
    by_key: Dict[tuple[str, str], Dict[str, Any]] = {}
    with ck_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            by_key[(rec["symbol"], rec["asof"])] = rec
    feat = pd.DataFrame(list(by_key.values()))
    out_path = feat_dir / FEATURES_NAME
    _atomic_write_parquet(feat, out_path)
    done_final = len(by_key)
    snap_done = {
        "done": done_final,
        "total": total_jobs,
        "pct": min(100.0, done_final / total_jobs * 100.0) if total_jobs else 100.0,
        "remaining": max(total_jobs - done_final, 0),
        "rate": None,
        "eta_sec": None,
        "complete": True,
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    _publish_progress(feat_dir, snap_done, progress_html)
    print(f"features -> {out_path} n={len(feat)}")
    return out_path


def _recompose_scores(feat: pd.DataFrame, spec: Dict[str, Any]) -> pd.DataFrame:
    out = feat.copy()
    scores = []
    for _, row in out.iterrows():
        breakdown = {k: row.get(f"b_{k}") for k in BUCKET_KEYS}
        if all(v is None or (isinstance(v, float) and pd.isna(v)) for v in breakdown.values()):
            scores.append(None)
            continue
        scores.append(composite_score(breakdown, spec, row.get("cli_total")))
    out["score"] = scores
    return out


def cmd_recompose(spec_path: Path, out_dir: Path, iteration: int, run_id: Optional[str], smoke: bool) -> Path:
    spec = _load_spec(spec_path)
    feat_path = out_dir / ("features_smoke" if smoke else "features") / FEATURES_NAME
    if not feat_path.exists():
        raise FileNotFoundError(f"Missing frozen features {feat_path}. Run build-features first.")
    feat = pd.read_parquet(feat_path)
    obs = _recompose_scores(feat, spec)
    iter_dir = _refuse_overwrite(out_dir / f"iter_{iteration:02d}", run_id)
    if run_id and iter_dir != out_dir / f"iter_{iteration:02d}":
        iter_dir.mkdir(parents=True, exist_ok=True)
    else:
        iter_dir.mkdir(parents=True, exist_ok=True)
    (iter_dir / "spec.json").write_text(json.dumps(spec, indent=2), encoding="utf-8")
    _atomic_write_parquet(obs, iter_dir / "observations.parquet")
    print(f"recompose -> {iter_dir}")
    return iter_dir


def _metrics_block(
    obs: pd.DataFrame,
    spec: Dict[str, Any],
    folds: Dict[str, Any],
    *,
    include_confirmation: bool,
    freeze_hash: Optional[str],
) -> Dict[str, Any]:
    eval_cfg = spec["evaluation"]
    horizon = 13
    min_names = int(eval_cfg.get("min_names_per_date", spec["universe"]["min_symbols"]))
    boot_n = int((eval_cfg.get("bootstrap") or {}).get("replicates", 10000))
    boot_block = int((eval_cfg.get("bootstrap") or {}).get("block_length_obs", 13))
    seed = int((eval_cfg.get("bootstrap") or {}).get("seed", DEFAULT_BOOTSTRAP_SEED))

    work = obs.copy()
    work["asof"] = pd.to_datetime(work["asof"]).dt.date
    work["score"] = pd.to_numeric(work["score"], errors="coerce")
    ret_col = f"fwd_{horizon}w"
    tgt_col = f"target_date_{horizon}w"
    work[ret_col] = pd.to_numeric(work[ret_col], errors="coerce")
    work[tgt_col] = pd.to_datetime(work[tgt_col], errors="coerce")

    if include_confirmation:
        raise ValueError(
            "REFUSED: development _metrics_block cannot open F5/F6. "
            "Use cmd_confirm after ChatGPT APPROVE of the confirmation gate."
        )

    fold_ids = list(DEVELOPMENT_FOLDS) + ["F5", "F6"]
    fold_tables = {}
    for fid in fold_ids:
        f = folds[fid]
        if fid in CONFIRMATION_FOLDS:
            fold_tables[fid] = {"sealed": True, "metrics": None}
            continue
        sub = work[(work["asof"] >= f["oos_start"]) & (work["asof"] <= f["oos_end"])]
        sub = filter_outcome_contained(sub, horizon, f["oos_end"])
        fold_tables[fid] = _slice_metrics(sub, spec, min_names, boot_n, boot_block, seed, ret_col)

    # development primary = F1-F4 contained, ex-VIN
    dev = []
    for fid in DEVELOPMENT_FOLDS:
        f = folds[fid]
        part = work[(work["asof"] >= f["oos_start"]) & (work["asof"] <= f["oos_end"])]
        part = filter_outcome_contained(part, horizon, f["oos_end"])
        dev.append(part)
    dev_df = pd.concat(dev, ignore_index=True) if dev else work.iloc[0:0]
    primary = _slice_metrics(
        dev_df[~dev_df["symbol"].isin(EX_VIN)],
        spec,
        min_names,
        boot_n,
        boot_block,
        seed,
        ret_col,
    )
    full = _slice_metrics(dev_df, spec, min_names, boot_n, boot_block, seed, ret_col)
    leave_f3 = _slice_metrics(
        dev_df[(dev_df["dev_fold"] != "F3") & (~dev_df["symbol"].isin(EX_VIN))]
        if "dev_fold" in dev_df.columns
        else dev_df[~dev_df["symbol"].isin(EX_VIN)],
        spec,
        min_names,
        boot_n,
        boot_block,
        seed,
        ret_col,
    )
    return {
        "schema_version": "2.0",
        "label": "RESEARCH_ONLY_NOT_PRODUCTION",
        "metric_role": "development_validation_ic",
        "primary_metric": "mean_date_level_exvin_spearman_ic_13w",
        "primary": primary,
        "full_development": full,
        "leave_F3_out_exvin": leave_f3,
        "folds": fold_tables,
        "include_confirmation": False,
        "n_score_null": int(work["score"].isna().sum()),
        "n_rows": int(len(work)),
    }


def _slice_metrics(
    sub: pd.DataFrame,
    spec: Dict[str, Any],
    min_names: int,
    boot_n: int,
    boot_block: int,
    seed: int,
    ret_col: str,
) -> Dict[str, Any]:
    ic_df = date_level_ic_and_spread(
        sub,
        score_col="score",
        ret_col=ret_col,
        min_names=min_names,
        min_per_quintile=int(spec["evaluation"].get("min_obs_per_quintile", 8)),
    )
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
    }


def cmd_evaluate(
    spec_path: Path,
    iter_dir: Path,
    include_confirmation: bool,
    spec_hash_arg: Optional[str],
) -> Path:
    if include_confirmation:
        raise SystemExit(
            "REFUSED: evaluate cannot open F5/F6. "
            "Use `confirm` after ChatGPT re-clears the confirmation gate."
        )
    spec = _load_spec(spec_path)
    obs_path = iter_dir / "observations.parquet"
    if not obs_path.exists():
        raise FileNotFoundError(obs_path)
    obs = pd.read_parquet(obs_path)
    panel_end = pd.to_datetime(obs["asof"]).max().date()
    folds = load_canonical_folds(panel_end)
    metrics = _metrics_block(
        obs,
        spec,
        folds,
        include_confirmation=False,
        freeze_hash=None,
    )
    out = iter_dir / "metrics.json"
    if out.exists():
        raise FileExistsError(f"Refusing to overwrite {out}")
    _json_dump(out, metrics)
    summary = [
        "# Structural TA predictive iteration (RESEARCH ONLY)",
        "",
        f"- metric_role: {metrics['metric_role']}",
        f"- primary mean date-level ex-VIN IC 13w: {metrics['primary'].get('mean_ic')}",
        f"- usable dates: {metrics['primary'].get('n_usable_dates')}",
        "- F5/F6: SEALED",
        "",
        "Not a buy/sell signal. Not production scoring.",
    ]
    (iter_dir / "SUMMARY.md").write_text("\n".join(summary), encoding="utf-8")
    print(f"evaluate -> {out}")
    return out


def _feat_identity_and_path(out_dir: Path) -> Tuple[Path, Dict[str, Any]]:
    feat_dir = out_dir / "features"
    feat_path = feat_dir / FEATURES_NAME
    id_path = feat_dir / IDENTITY_NAME
    if not feat_path.exists():
        raise FileNotFoundError(feat_path)
    identity_prev = (
        json.loads(id_path.read_text(encoding="utf-8")) if id_path.exists() else {}
    )
    return feat_path, identity_prev


def cmd_confirm_preflight(
    spec_path: Path,
    iter_dir: Path,
    freeze_hash: str,
    baseline_iter_dir: Path,
    out_dir: Path,
) -> Path:
    """Counts + hashes only. Never computes or prints F5/F6 IC."""
    spec = _load_spec(spec_path)
    assert_confirm_bindings(
        spec=spec, spec_path=spec_path, iter_dir=iter_dir, freeze_hash=freeze_hash
    )
    frozen = load_frozen_candidate(out_dir)
    if frozen.get("spec_hash") != freeze_hash:
        raise ValueError("freeze_hash != FROZEN_CANDIDATE.spec_hash")
    cand_path = iter_dir / "observations.parquet"
    base_path = baseline_iter_dir / "observations.parquet"
    if not cand_path.exists():
        raise FileNotFoundError(cand_path)
    if not base_path.exists():
        raise FileNotFoundError(base_path)
    metrics_path = iter_dir / CONFIRMATION_METRICS_NAME
    receipt_path = iter_dir / CONFIRMATION_RECEIPT_NAME
    lock_path = iter_dir / CONFIRM_LOCK_NAME
    spent_path = iter_dir / CONFIRMATION_SPENT_NAME
    if (
        metrics_path.exists()
        or receipt_path.exists()
        or lock_path.exists()
        or spent_path.exists()
    ):
        raise FileExistsError(
            f"Confirmation already disclosed, locked, or spent ({metrics_path.name}, "
            f"{receipt_path.name}, {lock_path.name}, or {spent_path.name}). "
            "One-shot gate refuses reuse."
        )
    cand = pd.read_parquet(cand_path)
    base = pd.read_parquet(base_path)
    panel_end = pd.to_datetime(cand["asof"]).max().date()
    folds = load_canonical_folds(panel_end)
    min_names = int(
        spec["evaluation"].get("min_names_per_date", spec["universe"]["min_symbols"])
    )
    baseline_spec_path = baseline_iter_dir / "spec.json"
    if not baseline_spec_path.exists():
        raise FileNotFoundError(baseline_spec_path)
    baseline_spec = _load_spec(baseline_spec_path)
    baseline_spec_hash = spec_hash(baseline_spec)
    feat_path, feat_identity = _feat_identity_and_path(out_dir)
    identity = build_confirm_identity_bundle(
        feat_path=feat_path,
        feat_identity=feat_identity,
        iter_dir=iter_dir,
        freeze_hash=freeze_hash,
        baseline_iter_dir=baseline_iter_dir,
        baseline_spec_hash=baseline_spec_hash,
        candidate_obs_path=cand_path,
        baseline_obs_path=base_path,
    )
    counts = confirm_preflight_counts(
        candidate_obs=cand,
        baseline_obs=base,
        folds=folds,
        min_names=min_names,
    )
    body = {
        "schema_version": "2.2_confirm_preflight",
        "label": "RESEARCH_ONLY_NOT_PRODUCTION",
        "ic_computed": False,
        "f5_f6_ic_disclosed": False,
        "identity": identity,
        "bindings": {
            "spec_hash": freeze_hash,
            "baseline_iter_dir": str(baseline_iter_dir),
            "candidate_iter_dir": str(iter_dir),
            "baseline_spec_hash": baseline_spec_hash,
        },
        "approved_snapshots": {
            "frozen_candidate_path": str(out_dir / FROZEN_CANDIDATE_NAME),
            "confirm_preflight_path": str(iter_dir / CONFIRM_PREFLIGHT_NAME),
        },
        "counts": counts,
        "gate_caveat": GATE_POST_HOC_CAVEAT,
        "note": (
            "Metrics-suppressed. ChatGPT must APPROVE confirmation gate before "
            "`confirm --authorize-chatgpt-reclear` may disclose F5/F6 IC."
        ),
    }
    out = iter_dir / CONFIRM_PREFLIGHT_NAME
    _json_dump(out, body)
    print(f"confirm-preflight -> {out} (no IC)")
    return out


def cmd_confirm(
    spec_path: Path,
    iter_dir: Path,
    freeze_hash: str,
    baseline_iter_dir: Path,
    out_dir: Path,
    authorize_chatgpt_reclear: bool,
    approved_preflight_sha256: str,
) -> Path:
    if not authorize_chatgpt_reclear:
        raise SystemExit(
            "REFUSED: F5/F6 remain sealed. Confirmation gate is patched but "
            "ChatGPT must re-clear first. Run `confirm-preflight` for hashes/counts, "
            "then after APPROVE: confirm --authorize-chatgpt-reclear "
            "--approved-preflight-sha256 <sha256> "
            "--baseline-iter-dir <iter_00>."
        )
    spec = _load_spec(spec_path)
    assert_confirm_bindings(
        spec=spec, spec_path=spec_path, iter_dir=iter_dir, freeze_hash=freeze_hash
    )
    cand_path = iter_dir / "observations.parquet"
    base_path = baseline_iter_dir / "observations.parquet"
    if not cand_path.exists() or not base_path.exists():
        raise FileNotFoundError("candidate and CLI baseline observations.parquet required")
    baseline_spec_path = baseline_iter_dir / "spec.json"
    if not baseline_spec_path.exists():
        raise FileNotFoundError(baseline_spec_path)
    baseline_spec = _load_spec(baseline_spec_path)
    baseline_spec_hash = spec_hash(baseline_spec)
    cand = pd.read_parquet(cand_path)
    base = pd.read_parquet(base_path)
    panel_end = pd.to_datetime(cand["asof"]).max().date()
    folds = load_canonical_folds(panel_end)
    feat_path, feat_identity = _feat_identity_and_path(out_dir)
    identity = build_confirm_identity_bundle(
        feat_path=feat_path,
        feat_identity=feat_identity,
        iter_dir=iter_dir,
        freeze_hash=freeze_hash,
        baseline_iter_dir=baseline_iter_dir,
        baseline_spec_hash=baseline_spec_hash,
        candidate_obs_path=cand_path,
        baseline_obs_path=base_path,
    )
    enforce_approved_snapshot(
        out_dir=out_dir,
        iter_dir=iter_dir,
        freeze_hash=freeze_hash,
        baseline_iter_dir=baseline_iter_dir,
        baseline_spec_hash=baseline_spec_hash,
        current_identity=identity,
        approved_preflight_sha256=approved_preflight_sha256,
    )
    lock_path = claim_confirmation_slot(iter_dir)
    try:
        artifact = build_confirmation_artifact(
            candidate_obs=cand,
            baseline_obs=base,
            candidate_spec=spec,
            baseline_spec=baseline_spec,
            folds=folds,
            identity=identity,
        )
        metrics_path = iter_dir / CONFIRMATION_METRICS_NAME
        receipt = {
            "schema_version": "2.3_confirm_receipt",
            "label": "RESEARCH_ONLY_NOT_PRODUCTION",
            "one_shot": True,
            "overwrite_forbidden": True,
            "readout": artifact.get("readout"),
            "identity": identity,
            "metrics_path": str(metrics_path),
            "approved_preflight_sha256": approved_preflight_sha256,
            "approved_snapshots": {
                "frozen_candidate_path": str(out_dir / FROZEN_CANDIDATE_NAME),
                "confirm_preflight_path": str(iter_dir / CONFIRM_PREFLIGHT_NAME),
            },
            "gate_caveat": GATE_POST_HOC_CAVEAT,
            "production_authorization": False,
        }
        metrics_path, receipt_path = finalize_confirmation_bundle(
            iter_dir, lock_path, artifact, receipt
        )
    except Exception as exc:
        mark_confirmation_spent(
            iter_dir,
            lock_path,
            reason=str(exc),
            approved_preflight_sha256=approved_preflight_sha256,
        )
        raise
    summary = [
        "# Structural TA confirmation (RESEARCH ONLY)",
        "",
        f"- readout: {artifact.get('readout')}",
        f"- primary_scope: {artifact.get('primary_scope')}",
        f"- primary ex-VIN mean IC (F5+F6): {artifact.get('primary', {}).get('mean_ic')}",
        f"- paired ex-VIN CLI delta mean: "
        f"{artifact.get('paired_exvin_delta_primary', {}).get('mean_delta')}",
        f"- paired full CLI delta mean: "
        f"{artifact.get('paired_full_delta_primary', {}).get('mean_delta')}",
        f"- F6 label: {F6_LABEL}",
        "",
        "Not a buy/sell signal. Not production scoring. One-shot holdout disclosed.",
    ]
    (iter_dir / "CONFIRMATION_SUMMARY.md").write_text("\n".join(summary), encoding="utf-8")
    print(f"confirm -> {metrics_path} readout={artifact.get('readout')}")
    return metrics_path


def cmd_record_freeze(
    spec_path: Path,
    iter_dir: Path,
    freeze_hash: str,
    out_dir: Path,
) -> Path:
    """Record frozen candidate after council REDIRECT; does not open F5/F6."""
    spec = _load_spec(spec_path)
    assert_confirm_bindings(
        spec=spec, spec_path=spec_path, iter_dir=iter_dir, freeze_hash=freeze_hash
    )
    out = out_dir / FROZEN_CANDIDATE_NAME
    if out.exists():
        prev = json.loads(out.read_text(encoding="utf-8"))
        if prev.get("spec_hash") != freeze_hash:
            raise FileExistsError(
                f"{out} exists with different hash {prev.get('spec_hash')}"
            )
        print(f"freeze already recorded -> {out}")
        return out
    body = {
        "schema_version": "2.1_frozen_candidate",
        "label": "RESEARCH_ONLY_NOT_PRODUCTION",
        "frozen_at": datetime.now().isoformat(timespec="seconds"),
        "spec_path": str(spec_path),
        "iter_dir": str(iter_dir),
        "spec_hash": freeze_hash,
        "f1_f4_search_stopped": True,
        "f5_f6_sealed": True,
        "confirm_authorized": False,
        "council": "ChatGPT+Opus+Fable REDIRECT 2026-08-29",
        "gate_caveat": GATE_POST_HOC_CAVEAT,
        "next": "confirm-preflight then ChatGPT re-clear before confirm",
    }
    _json_dump(out, body)
    print(f"freeze recorded -> {out}")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Structural TA predictive score loop (research)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_pf = sub.add_parser("preflight")
    p_pf.add_argument("--spec", type=Path, required=True)
    p_pf.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p_pf.add_argument("--smoke", action="store_true")

    p_bf = sub.add_parser("build-features")
    p_bf.add_argument("--spec", type=Path, required=True)
    p_bf.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p_bf.add_argument("--smoke", action="store_true")
    p_bf.add_argument("--resume", action="store_true")
    p_bf.add_argument(
        "--workers",
        type=int,
        default=1,
        help="ProcessPool workers for analyze_ticker (2 ≈ target 2x; frees parent panel first)",
    )

    p_st = sub.add_parser("status", help="Progress bar for build-features checkpoint")
    p_st.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p_st.add_argument("--smoke", action="store_true")
    p_st.add_argument("--watch", action="store_true", help="Refresh terminal bar until complete")
    p_st.add_argument("--interval", type=float, default=10.0, help="Watch refresh seconds")
    p_st.add_argument("--html", type=Path, default=None, help="HTML progress page path")
    p_st.add_argument(
        "--serve",
        type=int,
        nargs="?",
        const=8765,
        default=None,
        metavar="PORT",
        help="Serve features dir over HTTP for live JSON polling (default port 8765)",
    )

    p_rc = sub.add_parser("recompose")
    p_rc.add_argument("--spec", type=Path, required=True)
    p_rc.add_argument("--iteration", type=int, required=True)
    p_rc.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p_rc.add_argument("--run-id", default=None)
    p_rc.add_argument("--smoke", action="store_true")

    p_ev = sub.add_parser("evaluate")
    p_ev.add_argument("--spec", type=Path, required=True)
    p_ev.add_argument("--iter-dir", type=Path, required=True)

    p_cf = sub.add_parser("confirm")
    p_cf.add_argument("--spec", type=Path, required=True)
    p_cf.add_argument("--iter-dir", type=Path, required=True)
    p_cf.add_argument("--spec-hash", required=True)
    p_cf.add_argument(
        "--baseline-iter-dir",
        type=Path,
        required=True,
        help="CLI baseline iteration dir (usually iter_00) for paired delta",
    )
    p_cf.add_argument("--out", type=Path, default=DEFAULT_OUT)
    p_cf.add_argument(
        "--authorize-chatgpt-reclear",
        action="store_true",
        help="Required after ChatGPT APPROVE of the patched confirmation gate",
    )
    p_cf.add_argument(
        "--approved-preflight-sha256",
        required=True,
        help="SHA256 of reviewed confirm_preflight.json (immutable hash-pin)",
    )

    p_cfp = sub.add_parser(
        "confirm-preflight",
        help="Hashes + F5/F6 date/row counts only; never computes IC",
    )
    p_cfp.add_argument("--spec", type=Path, required=True)
    p_cfp.add_argument("--iter-dir", type=Path, required=True)
    p_cfp.add_argument("--spec-hash", required=True)
    p_cfp.add_argument("--baseline-iter-dir", type=Path, required=True)
    p_cfp.add_argument("--out", type=Path, default=DEFAULT_OUT)

    p_fz = sub.add_parser("record-freeze", help="Record frozen candidate; keeps F5/F6 sealed")
    p_fz.add_argument("--spec", type=Path, required=True)
    p_fz.add_argument("--iter-dir", type=Path, required=True)
    p_fz.add_argument("--spec-hash", required=True)
    p_fz.add_argument("--out", type=Path, default=DEFAULT_OUT)

    # Legacy alias: refuse to run old all-in-one path
    p_run = sub.add_parser("run")
    p_run.add_argument("--spec", type=Path, required=True)
    p_run.add_argument("--iteration", type=int, required=True)
    p_run.add_argument("--out", type=Path, default=DEFAULT_OUT)

    args = parser.parse_args()
    if args.cmd == "preflight":
        cmd_preflight(args.spec, args.out, args.smoke)
    elif args.cmd == "build-features":
        cmd_build_features(args.spec, args.out, args.smoke, args.resume, args.workers)
    elif args.cmd == "status":
        cmd_status(args.out, args.smoke, args.watch, args.interval, args.html, args.serve)
    elif args.cmd == "recompose":
        cmd_recompose(args.spec, args.out, args.iteration, args.run_id, args.smoke)
    elif args.cmd == "evaluate":
        cmd_evaluate(args.spec, args.iter_dir, False, None)
    elif args.cmd == "confirm-preflight":
        cmd_confirm_preflight(
            args.spec, args.iter_dir, args.spec_hash, args.baseline_iter_dir, args.out
        )
    elif args.cmd == "record-freeze":
        cmd_record_freeze(args.spec, args.iter_dir, args.spec_hash, args.out)
    elif args.cmd == "confirm":
        cmd_confirm(
            args.spec,
            args.iter_dir,
            args.spec_hash,
            args.baseline_iter_dir,
            args.out,
            args.authorize_chatgpt_reclear,
            args.approved_preflight_sha256,
        )
    elif args.cmd == "run":
        raise SystemExit(
            "REFUSED: legacy `run` is disabled after ChatGPT REDIRECT. "
            "Use preflight -> build-features -> recompose -> evaluate. "
            "Do not compute IC until preflight stop-condition passes."
        )


if __name__ == "__main__":
    main()
