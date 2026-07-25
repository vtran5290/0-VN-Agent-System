"""B0_CLEAN runner — smoke / research-only. No network. No live paths."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

REPO = Path(__file__).resolve().parents[3]
PANEL_PATH = REPO / "data" / "fireant_ssot" / "ta_ohlcv_panel.parquet"
VNI_PATH = REPO / "data" / "fireant_ssot" / "ta_vnindex.parquet"

from .execution import simulate_panel
from .metrics import (
    aggregate_metrics_table,
    per_ticker_metrics,
    summarize_trades,
    vin_sensitivity,
    year_regime_metrics,
)
from .signals import prepare_panel_with_signals
from .universe import apply_universe_panel
from src.research._ssot_guard import PanelNotCertified, assert_panel_certified

SMOKE_SYMBOLS = ["FPT", "VCB", "SSI", "HPG", "MWG", "ACB", "VND", "DGC", "VHM"]


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _git_meta() -> dict[str, Any]:
    meta: dict[str, Any] = {"commit": None, "dirty": None}
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO, text=True, stderr=subprocess.DEVNULL
        ).strip()
        dirty = subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=REPO, text=True, stderr=subprocess.DEVNULL
        ).strip()
        meta["commit"] = commit
        meta["dirty"] = bool(dirty)
    except Exception as exc:
        meta["error"] = str(exc)
    return meta


def load_ssot(
    symbols: Iterable[str] | None = None,
    start: str | None = None,
    end: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    cols = [
        "symbol",
        "date",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "value",
        "close_raw",
        "ca_suspect",
        "unit_vnd",
        "source",
        "adjust_basis",
    ]
    panel = pd.read_parquet(PANEL_PATH, columns=cols)
    panel["date"] = pd.to_datetime(panel["date"])
    if symbols is not None:
        syms = {s.upper() for s in symbols}
        panel = panel[panel["symbol"].astype(str).str.upper().isin(syms)]
    if start:
        panel = panel[panel["date"] >= pd.Timestamp(start)]
    if end:
        panel = panel[panel["date"] <= pd.Timestamp(end)]

    vni = pd.read_parquet(VNI_PATH)
    vni["date"] = pd.to_datetime(vni["date"])
    # Need lookback before start for indicators — caller should load warm-up separately if needed
    return panel.reset_index(drop=True), vni.reset_index(drop=True)


def load_ssot_with_warmup(
    symbols: Iterable[str],
    start: str,
    end: str,
    warmup_calendar_days: int = 400,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    warm_start = (pd.Timestamp(start) - pd.Timedelta(days=warmup_calendar_days)).strftime("%Y-%m-%d")
    panel, vni = load_ssot(symbols=symbols, start=warm_start, end=end)
    return panel, vni


def run_b0(
    panel: pd.DataFrame,
    vnindex: pd.DataFrame,
    *,
    ablation: str = "primary",
    signal_start: str | None = None,
    signal_end: str | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    uni = apply_universe_panel(panel)
    sig = prepare_panel_with_signals(uni, vnindex, ablation=ablation)
    if signal_start:
        # Keep history for indicators but only allow signals in window
        mask = sig["date"] < pd.Timestamp(signal_start)
        sig.loc[mask, "signal"] = False
    if signal_end:
        mask = sig["date"] > pd.Timestamp(signal_end)
        sig.loc[mask, "signal"] = False
    trades = simulate_panel(sig)
    return sig, trades


def write_smoke_artifacts(
    out_dir: Path,
    trades: pd.DataFrame,
    *,
    symbols: list[str],
    start: str,
    end: str,
    extra_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = summarize_trades(trades)
    per_ticker = per_ticker_metrics(trades)
    year_m = year_regime_metrics(trades)
    vin_m = vin_sensitivity(trades)
    agg = aggregate_metrics_table(summary)

    trades_path = out_dir / "trade_events_B0.parquet"
    trades.to_parquet(trades_path, index=False)
    per_ticker.to_csv(out_dir / "per_ticker_metrics.csv", index=False)
    agg.to_csv(out_dir / "aggregate_metrics.csv", index=False)
    year_m.to_csv(out_dir / "year_regime_metrics.csv", index=False)
    vin_m.to_csv(out_dir / "vin_sensitivity.csv", index=False)

    import numpy
    import pandas as pd_mod

    manifest: dict[str, Any] = {
        "run_type": "B0_CLEAN_SMOKE",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "research_only": True,
        "live_paths_touched": False,
        "family": "B0_CLEAN",
        "alpha_multiplicity_member": False,
        "b0_repro_status": "BLOCKED_BY_MISSING_CANONICAL",
        "git": _git_meta(),
        "source_panel": {
            "path": "data/fireant_ssot/ta_ohlcv_panel.parquet",
            "sha256": _sha256(PANEL_PATH),
        },
        "source_vnindex": {
            "path": "data/fireant_ssot/ta_vnindex.parquet",
            "sha256": _sha256(VNI_PATH),
        },
        "smoke_window": {"start": start, "end": end, "symbols": symbols},
        "formulas": {
            "adv50": "mean(value, T-49..T) > 2e9 raw VND",
            "rsi14": "Wilder EWM alpha=1/14 adjust=False min_periods=14",
            "entry": "open T+1",
            "exit": "close of 3rd session after signal T",
            "primary_cell": "EX_VIN x 45bp, entries >= 2022-08-29",
            "ca_policy": "exclude signal day ca_suspect + holding-window ca_suspect (proxy; no dated ex-dates)",
        },
        "costs_bp": [30, 45, 60],
        "attempted_spec_count": 1,
        "package_versions": {
            "python": sys.version.split()[0],
            "pandas": pd_mod.__version__,
            "numpy": numpy.__version__,
        },
        "sanity": summary,
        "caveats": [
            "CA calendar is proxy (ca_suspect); residual CA risk remains",
            "No PIT security master — ETF prefix heuristic only; exchange cells are proxy",
            "VNINDEX coverage may end before panel max_date",
            "Do not interpret smoke as ADVANCE/REJECT verdict",
        ],
    }
    if extra_manifest:
        manifest.update(extra_manifest)

    (out_dir / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    report = _smoke_report_md(manifest, summary, per_ticker, vin_m)
    (out_dir / "final_research_report.md").write_text(report, encoding="utf-8")
    return manifest


def _smoke_report_md(
    manifest: dict[str, Any],
    summary: dict[str, Any],
    per_ticker: pd.DataFrame,
    vin_m: pd.DataFrame,
) -> str:
    lines = [
        "# B0_CLEAN Smoke Report (facts only — NOT a verdict)",
        "",
        f"Generated: {manifest.get('generated_at_utc')}",
        f"Window: {manifest.get('smoke_window')}",
        f"research_only={manifest.get('research_only')} live_paths_touched={manifest.get('live_paths_touched')}",
        f"B0_REPRO: {manifest.get('b0_repro_status')}",
        "",
        "## Sanity snapshot",
        "",
        f"- signals attempted: {summary.get('n_signals_attempted')}",
        f"- filled: {summary.get('n_filled')}",
        f"- % ENTRY_LOCKED_NO_FILL: {summary.get('pct_entry_locked')}",
        f"- % ENTRY_NO_VOL: {summary.get('pct_entry_no_vol')}",
        f"- % CA_WINDOW_EXCLUDED: {summary.get('pct_ca_excluded')}",
        f"- % SETTLEMENT_T3_ERA: {summary.get('pct_settlement_t3_era')}",
        f"- same-close fills: {summary.get('same_close_fills')} (must be 0)",
        "",
        "### Primary read proxy (T2-era EX_VIN @ 45bp)",
        "",
        "```json",
        json.dumps(summary.get("primary_T2_EX_VIN"), indent=2, default=str),
        "```",
        "",
        "### FULL T2 vs EX_VIN",
        "",
        vin_m.to_string(index=False) if not vin_m.empty else "(none)",
        "",
        "### Top tickers by trade count",
        "",
        per_ticker.head(15).to_string(index=False) if not per_ticker.empty else "(none)",
        "",
        "## Flags for Claude (not conclusions)",
        "",
        "- Compare fill rate and cost drag (gross vs net@45bp); large drag or impossible means ⇒ units/cost bug.",
        "- Any same-close fill ⇒ lookahead/fill-clock bug.",
        "- Smoke scale only — do not ADVANCE/REJECT.",
        "",
    ]
    return "\n".join(str(x) for x in lines)


def main_smoke() -> int:
    # Refuse to run on a drifted / uncertified SSOT panel
    sha = assert_panel_certified()
    print(f"[ssot_guard] panel certified sha={sha[:16]}…")

    start, end = "2023-01-01", "2024-12-31"
    symbols = SMOKE_SYMBOLS
    out_dir = REPO / "outputs" / "research" / "tplus_adv50" / "2026-07-23_B0_smoke"

    panel, vni = load_ssot_with_warmup(symbols, start, end)
    _, trades = run_b0(panel, vni, signal_start=start, signal_end=end)
    write_smoke_artifacts(out_dir, trades, symbols=symbols, start=start, end=end)
    print(f"wrote {out_dir}")
    print(f"trades={len(trades)} filled={(trades['filled']==True).sum() if len(trades) else 0}")  # noqa: E712
    return 0


def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(description="B0_CLEAN research runner")
    p.add_argument("--smoke", action="store_true", help="Phase-A smoke subset (required)")
    args = p.parse_args(argv)
    if not args.smoke:
        p.error("Phase A entrypoint requires --smoke (full history is a separate handoff)")
    try:
        return main_smoke()
    except PanelNotCertified as exc:
        print(f"PanelNotCertified: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
