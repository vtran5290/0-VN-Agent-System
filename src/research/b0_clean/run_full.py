"""B0_CLEAN Phase B — full-history research run (facts only)."""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from .execution import ExecConfig, simulate_panel
from .metrics import summarize_trades, vin_sensitivity, year_regime_metrics
from .phase_b_metrics import (
    aggregate_extended,
    capacity_metrics,
    leave_one_out,
    multiple_testing_table,
    per_ticker_metrics_full,
    period_window_metrics,
    portfolio_weight_views,
    top_ticker_contribution,
)
from .run import REPO, VNI_PATH, _git_meta, _sha256, run_b0
from .signals import apply_signal_gates
from src.research._ssot_guard import PanelNotCertified, assert_panel_certified

FULL_START = "2017-01-01"
FULL_END = "2026-07-23"
OUT_DIR = REPO / "outputs" / "research" / "tplus_adv50" / "2026-07-23_B0_full"


def load_ssot_all(start: str, end: str, warmup_calendar_days: int = 500) -> tuple[pd.DataFrame, pd.DataFrame]:
    warm_start = (pd.Timestamp(start) - pd.Timedelta(days=warmup_calendar_days)).strftime("%Y-%m-%d")
    from .run import load_ssot

    return load_ssot(symbols=None, start=warm_start, end=end)


def run_primary() -> tuple[pd.DataFrame, pd.DataFrame, str]:
    sha = assert_panel_certified()
    print(f"[ssot_guard] certified sha={sha[:16]}…", flush=True)
    t0 = time.time()
    panel, vni = load_ssot_all(FULL_START, FULL_END)
    print(
        f"[load] panel rows={len(panel)} symbols={panel['symbol'].nunique()} in {time.time()-t0:.1f}s",
        flush=True,
    )
    t1 = time.time()
    sig, trades = run_b0(panel, vni, signal_start=FULL_START, signal_end=FULL_END)
    print(
        f"[primary] signals={int(sig['signal'].sum())} trade_rows={len(trades)} "
        f"filled={(trades['filled']==True).sum() if len(trades) else 0} "  # noqa: E712
        f"in {time.time()-t1:.1f}s",
        flush=True,
    )
    return sig, trades, sha


def run_horizon(sig_primary: pd.DataFrame, exit_sessions: int) -> pd.DataFrame:
    cfg = ExecConfig(exit_sessions_after_signal=exit_sessions)
    return simulate_panel(sig_primary, cfg=cfg)


def write_full_artifacts(
    trades: pd.DataFrame,
    *,
    sha: str,
    ablation_summaries: dict[str, Any],
    horizon_tables: dict[str, pd.DataFrame],
    n_signals_panel: int,
) -> dict[str, Any]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = summarize_trades(trades)
    print("[metrics] per-ticker + bootstrap…", flush=True)
    per_ticker = per_ticker_metrics_full(trades)
    agg = aggregate_extended(trades)
    year_m = year_regime_metrics(trades)
    vin_m = vin_sensitivity(trades)
    mt = multiple_testing_table(per_ticker)
    period = period_window_metrics(trades, asof=FULL_END)
    cap = capacity_metrics(trades)
    loo = leave_one_out(trades)
    top = top_ticker_contribution(trades)
    port = portfolio_weight_views(trades)

    trades.to_parquet(OUT_DIR / "trade_events_B0.parquet", index=False)
    per_ticker.to_csv(OUT_DIR / "per_ticker_metrics.csv", index=False)
    agg.to_csv(OUT_DIR / "aggregate_metrics.csv", index=False)
    year_m.to_csv(OUT_DIR / "year_regime_metrics.csv", index=False)
    vin_m.to_csv(OUT_DIR / "vin_sensitivity.csv", index=False)
    mt.to_csv(OUT_DIR / "multiple_testing.csv", index=False)
    period.to_csv(OUT_DIR / "period_window_metrics.csv", index=False)
    cap.to_csv(OUT_DIR / "capacity_metrics.csv", index=False)
    loo.to_csv(OUT_DIR / "leave_one_out.csv", index=False)
    top.to_csv(OUT_DIR / "top_ticker_contribution.csv", index=False)
    port.to_csv(OUT_DIR / "portfolio_weight_views.csv", index=False)

    hz_rows = []
    for name, ht in horizon_tables.items():
        s = summarize_trades(ht)
        block = s.get("primary_T2_EX_VIN") or {}
        hz_rows.append(
            {
                "exit_horizon": name,
                "primary": name == "T+3",
                "n_filled_T2_EX_VIN": block.get("n", 0),
                "mean_gross": block.get("mean_gross"),
                "mean_net_45bp": block.get("mean_net_45bp"),
                "pf_net_45bp": block.get("pf_net_45bp"),
                "hit_rate": block.get("hit_rate"),
            }
        )
    hz = pd.DataFrame(hz_rows)
    hz.to_csv(OUT_DIR / "exit_horizon_sensitivity.csv", index=False)

    abl_rows = []
    for name, s in ablation_summaries.items():
        block = s.get("primary_T2_EX_VIN") or {}
        abl_rows.append(
            {
                "ablation": name,
                "n": block.get("n", 0),
                "mean_net_45bp": block.get("mean_net_45bp"),
                "pf_net_45bp": block.get("pf_net_45bp"),
                "hit_rate": block.get("hit_rate"),
            }
        )
    pd.DataFrame(abl_rows).to_csv(OUT_DIR / "ablation_metrics.csv", index=False)

    import numpy as np_mod
    import pandas as pd_mod

    manifest: dict[str, Any] = {
        "run_type": "B0_CLEAN_FULL",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "research_only": True,
        "live_paths_touched": False,
        "alpha_multiplicity_member": False,
        "family": "B0_CLEAN",
        "b0_repro_status": "BLOCKED_BY_MISSING_CANONICAL",
        "git": _git_meta(),
        "source_panel": {
            "path": "data/fireant_ssot/ta_ohlcv_panel.parquet",
            "sha256": sha,
            "manifest_sha256": _sha256(REPO / "data" / "fireant_ssot" / "manifest.json"),
        },
        "source_vnindex": {
            "path": "data/fireant_ssot/ta_vnindex.parquet",
            "sha256": _sha256(VNI_PATH),
        },
        "window": {"signal_start": FULL_START, "signal_end": FULL_END},
        "formulas": {
            "adv50": "mean(value, T-49..T) > 2e9 raw VND",
            "rsi14": "Wilder EWM alpha=1/14",
            "entry": "open T+1",
            "exit_primary": "close of 3rd session after signal T",
            "primary_cell": "EX_VIN x 45bp, entries >= 2022-08-29",
            "ca_policy": "ca_suspect proxy exclusion (no dated ex-dates)",
        },
        "costs_bp": [30, 45, 60],
        "attempted_spec_count": 1 + len(ablation_summaries) + max(0, len(horizon_tables) - 1),
        "package_versions": {
            "python": sys.version.split()[0],
            "pandas": pd_mod.__version__,
            "numpy": np_mod.__version__,
        },
        "sanity": summary,
        "n_signal_bars": n_signals_panel,
        "caveats": [
            "CA calendar is proxy (ca_suspect); residual CA risk remains",
            "No PIT security master — ETF prefix heuristic; exchange cells proxy",
            "B0 is a benchmark — NO ADVANCE/REJECT / viability conclusion in this pack",
            "Exit-horizon and ablation tables are reporting-only; T+3 remains primary",
        ],
    }
    (OUT_DIR / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    report = _report_md(manifest, summary, agg, period, hz, per_ticker)
    (OUT_DIR / "final_research_report.md").write_text(report, encoding="utf-8")
    return manifest


def _report_md(
    manifest: dict[str, Any],
    summary: dict[str, Any],
    agg: pd.DataFrame,
    period: pd.DataFrame,
    hz: pd.DataFrame,
    per_ticker: pd.DataFrame,
) -> str:
    lines = [
        "# B0_CLEAN Full-History Report (facts only — NOT a verdict)",
        "",
        f"Generated: {manifest.get('generated_at_utc')}",
        f"Window: {manifest.get('window')}",
        f"research_only={manifest.get('research_only')} live_paths_touched={manifest.get('live_paths_touched')} "
        f"alpha_multiplicity_member={manifest.get('alpha_multiplicity_member')}",
        f"panel_sha: {manifest.get('source_panel', {}).get('sha256', '')[:16]}…",
        "",
        "## Sanity snapshot",
        "",
        f"- signals attempted (trade rows): {summary.get('n_signals_attempted')}",
        f"- filled: {summary.get('n_filled')}",
        f"- % ENTRY_LOCKED_NO_FILL: {summary.get('pct_entry_locked')}",
        f"- % ENTRY_NO_VOL: {summary.get('pct_entry_no_vol')}",
        f"- % CA_WINDOW_EXCLUDED: {summary.get('pct_ca_excluded')}",
        f"- % SETTLEMENT_T3_ERA: {summary.get('pct_settlement_t3_era')}",
        f"- same-close fills: {summary.get('same_close_fills')}",
        "",
        "### Primary cell proxy (T2 EX_VIN @ 45bp)",
        "",
        "```json",
        json.dumps(summary.get("primary_T2_EX_VIN"), indent=2, default=str),
        "```",
        "",
        "### Aggregate cells",
        "",
        agg.to_string(index=False) if not agg.empty else "(none)",
        "",
        "### Period windows (T2_primary)",
        "",
        period[period["era"] == "T2_primary"].to_string(index=False) if not period.empty else "(none)",
        "",
        "### Exit-horizon sensitivity (reporting only; T+3 primary)",
        "",
        hz.to_string(index=False) if not hz.empty else "(none)",
        "",
        "### Top tickers by n_filled (T2)",
        "",
        per_ticker.head(15).to_string(index=False) if not per_ticker.empty else "(none)",
        "",
        "## Explicit non-conclusions",
        "",
        "- This pack does **not** ADVANCE, REJECT, or declare viability.",
        "- B0 is excluded from alpha-multiplicity; Claude owns interpretation.",
        "",
    ]
    return "\n".join(str(x) for x in lines)


def main_full() -> int:
    try:
        sig, trades, sha = run_primary()
    except PanelNotCertified as exc:
        print(f"PanelNotCertified: {exc}", file=sys.stderr)
        return 3

    # Restrict signal window already applied in run_b0; reuse frame
    window_mask = (sig["date"] < pd.Timestamp(FULL_START)) | (sig["date"] > pd.Timestamp(FULL_END))
    sig_window = sig.copy()
    sig_window.loc[window_mask, "signal"] = False

    print("[horizons] T+2 / T+3 / T+5 …", flush=True)
    horizon_tables = {
        "T+2": run_horizon(sig_window, 2),
        "T+3": trades,
        "T+5": run_horizon(sig_window, 5),
    }

    print("[ablations] no_rsi / no_low_vol / no_vnindex …", flush=True)
    ablation_summaries: dict[str, Any] = {"primary": summarize_trades(trades)}
    for abl in ("no_rsi", "no_low_vol", "no_vnindex"):
        sig_ab = apply_signal_gates(sig_window, ablation=abl)
        sig_ab.loc[window_mask, "signal"] = False
        t_ab = simulate_panel(sig_ab)
        ablation_summaries[abl] = summarize_trades(t_ab)
        print(f"  {abl}: filled={(t_ab['filled']==True).sum() if len(t_ab) else 0}", flush=True)  # noqa: E712

    write_full_artifacts(
        trades,
        sha=sha,
        ablation_summaries=ablation_summaries,
        horizon_tables=horizon_tables,
        n_signals_panel=int(sig_window["signal"].sum()),
    )
    print(f"wrote {OUT_DIR}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main_full())
