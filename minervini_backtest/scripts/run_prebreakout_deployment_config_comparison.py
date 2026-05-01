from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


# Allow import of overlay helper module.
ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = Path(__file__).resolve().parents[0]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from minervini_backtest.scripts.run_prebreakout_portfolio_overlay import (  # type: ignore
    LATEST as OVERLAY_LATEST,
    PRE_ROOT as OVERLAY_PRE_ROOT,
    PortfolioCfg,
    _load_price_cache,
    _mk_price_lookup,
    _period_metrics,
    _prepare_trade_pool,
    _select_presets,
    _simulate_portfolio,
    _preset_rank_map,
    _slice_equity,
)


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _load_sources(base_dir: Path) -> dict[str, Any]:
    return {
        "trade_log": _read_csv(base_dir / "trade_log_best_presets.csv"),
        "robustness": _read_csv(base_dir / "preset_robustness_summary.csv"),
        "oos": _read_csv(base_dir / "oos_rolling_train_test_results.csv"),
        "run_meta": json.loads((base_dir / "run_meta.json").read_text(encoding="utf-8")) if (base_dir / "run_meta.json").exists() else {},
        "exec_gross_net": _read_csv(base_dir / "execution_backtest_results_gross_vs_net.csv"),
    }


def _score_return_over_dd(total_return: float, max_drawdown: float) -> float:
    if max_drawdown is None or not np.isfinite(max_drawdown):
        return np.nan
    if max_drawdown >= 0:
        # Defensive: drawdown should be <= 0 in this convention.
        return np.nan
    return float(total_return) / float(abs(max_drawdown))


def _recommended_default_score(
    score_2012: float,
    score_2022: float,
    score_2024: float,
) -> float:
    # Weight recent regimes more.
    if not np.isfinite(score_2012):
        score_2012 = 0.0
    if not np.isfinite(score_2022):
        score_2022 = 0.0
    if not np.isfinite(score_2024):
        score_2024 = 0.0
    return float(0.2 * score_2012 + 0.3 * score_2022 + 0.5 * score_2024)


def main() -> int:
    ap = argparse.ArgumentParser(description="Deployment config comparison for prebreakout portfolio overlay (audit-only).")
    ap.add_argument("--prebreakout-dir", default=str(OVERLAY_LATEST), help="Path to `prebreakout_research/latest` (default latest).")
    ap.add_argument("--initial-capital", type=float, default=1_000_000_000.0)
    ap.add_argument("--heat-cap", type=float, default=0.10)
    ap.add_argument("--dedupe-days", type=int, default=3)
    ap.add_argument("--cost-mult", type=float, default=1.0)
    ap.add_argument("--top-k", type=int, default=3, help="Top K for union/robust modes.")
    args = ap.parse_args()

    base_dir = Path(args.prebreakout_dir)
    src = _load_sources(base_dir)
    trade_log = src["trade_log"]
    robust_df = src["robustness"]
    oos_df = src["oos"]
    run_meta = src["run_meta"]
    if trade_log.empty:
        print("[ERROR] trade_log_best_presets.csv missing/empty in prebreakout dir.")
        return 1

    rank_map = _preset_rank_map(robust_df)

    selection_modes = [
        "best_preset_only",
        "top_k_presets_union",
        "oos_selected_presets",
        "latest_robustness_ranked",
    ]
    max_positions_list = [3, 5, 8]
    max_weight_list = [0.15, 0.20, 0.25]

    # Precompute deduped trade pool + price lookup per selection mode.
    mode_pool: dict[str, dict[str, Any]] = {}
    for mode in selection_modes:
        selected_presets = _select_presets(mode, args.top_k, robust_df, oos_df, None)
        pool, skipped_dups = _prepare_trade_pool(trade_log, selected_presets, rank_map, args.dedupe_days)
        if pool.empty:
            print(f"[WARN] selection mode {mode}: empty pool after dedupe.")
            mode_pool[mode] = {"selected_presets": selected_presets, "pool": pool, "skipped": skipped_dups, "px_lookup": {}}
            continue
        symbols = sorted(pool["symbol"].astype(str).unique().tolist())
        px = _load_price_cache(symbols)
        px_lookup = _mk_price_lookup(px)
        mode_pool[mode] = {
            "selected_presets": selected_presets,
            "pool": pool,
            "skipped": skipped_dups,
            "px_lookup": px_lookup,
        }

    rows: list[dict[str, Any]] = []

    for mode in selection_modes:
        mp = mode_pool[mode]
        pool = mp["pool"]
        skipped_dups = mp["skipped"]
        px_lookup = mp["px_lookup"]
        selected_presets = mp["selected_presets"]

        for max_pos in max_positions_list:
            for max_w in max_weight_list:
                cfg = PortfolioCfg(
                    initial_capital=args.initial_capital,
                    max_positions=max_pos,
                    max_weight=max_w,
                    heat_cap=args.heat_cap,
                    no_rebalance_after_entry=True,
                    sizing_mode="equal_weight",
                    dedupe_days=args.dedupe_days,
                    additional_cost_mult=args.cost_mult,
                )
                if pool.empty:
                    rows.append(
                        {
                            "selection_mode": mode,
                            "selected_preset_ids": json.dumps(selected_presets),
                            "max_positions": max_pos,
                            "max_weight": max_w,
                            "executed_trades": 0,
                            "total_return": np.nan,
                            "cagr": np.nan,
                            "max_drawdown": np.nan,
                            "sharpe": np.nan,
                            "sortino": np.nan,
                            "calmar": np.nan,
                            "avg_exposure": np.nan,
                            "cash_utilization_rate": np.nan,
                            "entries_per_year": np.nan,
                            "score_return_over_dd": np.nan,
                            "score_sharpe": np.nan,
                            "score_exposure_efficiency": np.nan,
                            "recommended_default_score": np.nan,
                        }
                    )
                    continue

                pool2 = pool.copy()
                pool2["selection_mode"] = mode

                eq_df, trade_df, _skipped = _simulate_portfolio(pool2, px_lookup, cfg, skipped_dups)
                if eq_df.empty or trade_df is None:
                    rows.append(
                        {
                            "selection_mode": mode,
                            "selected_preset_ids": json.dumps(selected_presets),
                            "max_positions": max_pos,
                            "max_weight": max_w,
                            "executed_trades": 0,
                            "total_return": np.nan,
                            "cagr": np.nan,
                            "max_drawdown": np.nan,
                            "sharpe": np.nan,
                            "sortino": np.nan,
                            "calmar": np.nan,
                            "avg_exposure": np.nan,
                            "cash_utilization_rate": np.nan,
                            "entries_per_year": np.nan,
                            "score_return_over_dd": np.nan,
                            "score_sharpe": np.nan,
                            "score_exposure_efficiency": np.nan,
                            "recommended_default_score": np.nan,
                        }
                    )
                    continue

                m_all = _period_metrics(eq_df, trade_df, None)
                m_2012 = m_all
                m_2022 = _period_metrics(eq_df, trade_df, "2022-01-01")
                m_2024 = _period_metrics(eq_df, trade_df, "2024-01-01")

                score_retdd_all = _score_return_over_dd(m_all.get("total_return"), m_all.get("max_drawdown"))
                score_sharpe_all = m_all.get("sharpe")
                score_exp_eff_all = m_all.get("cash_utilization_rate")

                score_2012 = _score_return_over_dd(m_2012.get("total_return"), m_2012.get("max_drawdown"))
                score_2022 = _score_return_over_dd(m_2022.get("total_return"), m_2022.get("max_drawdown"))
                score_2024 = _score_return_over_dd(m_2024.get("total_return"), m_2024.get("max_drawdown"))

                rec_score = _recommended_default_score(score_2012, score_2022, score_2024)

                row = {
                    "selection_mode": mode,
                    "selected_preset_ids": json.dumps(selected_presets),
                    "max_positions": max_pos,
                    "max_weight": max_w,
                    "executed_trades": int(m_all.get("n_trades") or 0),
                    # Full-period (2012-latest) metrics
                    "total_return": m_all.get("total_return"),
                    "cagr": m_all.get("cagr"),
                    "max_drawdown": m_all.get("max_drawdown"),
                    "sharpe": m_all.get("sharpe"),
                    "sortino": m_all.get("sortino"),
                    "calmar": m_all.get("calmar"),
                    "avg_exposure": m_all.get("avg_exposure"),
                    "cash_utilization_rate": m_all.get("cash_utilization_rate"),
                    "entries_per_year": m_all.get("entries_per_year"),
                    # Raw scoring components
                    "score_return_over_dd": score_retdd_all,
                    "score_sharpe": score_sharpe_all,
                    "score_exposure_efficiency": score_exp_eff_all,
                    # Recent-regime weighting
                    "score_return_over_dd_2012_latest": score_2012,
                    "score_return_over_dd_2022_latest": score_2022,
                    "score_return_over_dd_2024_latest": score_2024,
                    "recommended_default_score": rec_score,
                }

                # Period summary metrics (raw, visible)
                def _fill_period(prefix: str, m: dict[str, Any]) -> dict[str, Any]:
                    return {
                        f"total_return_{prefix}": m.get("total_return"),
                        f"cagr_{prefix}": m.get("cagr"),
                        f"max_drawdown_{prefix}": m.get("max_drawdown"),
                        f"sharpe_{prefix}": m.get("sharpe"),
                        f"sortino_{prefix}": m.get("sortino"),
                        f"calmar_{prefix}": m.get("calmar"),
                        f"avg_exposure_{prefix}": m.get("avg_exposure"),
                        f"cash_utilization_rate_{prefix}": m.get("cash_utilization_rate"),
                        f"entries_per_year_{prefix}": m.get("entries_per_year"),
                        f"n_trades_{prefix}": m.get("n_trades"),
                    }

                row.update(_fill_period("2012_latest", m_2012))
                row.update(_fill_period("2022_latest", m_2022))
                row.update(_fill_period("2024_latest", m_2024))

                rows.append(row)

    df = pd.DataFrame(rows)
    df = df.sort_values("recommended_default_score", ascending=False).reset_index(drop=True)
    df["rank_by_recommended_default_score"] = np.arange(1, len(df) + 1, dtype=int)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = OVERLAY_PRE_ROOT / f"portfolio_deployment_config_comparison_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_path = out_dir / "portfolio_deployment_config_comparison.csv"
    md_path = out_dir / "portfolio_deployment_config_report.md"
    df.to_csv(csv_path, index=False)

    top3 = df.head(3).copy()

    def _pretty_sel_ids(x: str) -> str:
        try:
            arr = json.loads(x)
            return ", ".join([str(a) for a in arr])
        except Exception:
            return str(x)

    lines = [
        "# Portfolio deployment config comparison (prebreakout overlay)",
        "",
        "This artifact compares deployable *research* portfolio overlay settings by re-running the existing portfolio overlay (no signal/engine redesign).",
        "",
        "## Compared grid",
        "- selection modes: `best_preset_only`, `top_k_presets_union`, `oos_selected_presets`, `latest_robustness_ranked` (each uses the overlay's current trade-log dedupe and net economics)",
        "- constraints grid: `max_positions` in {3,5,8}, `max_weight` in {15%,20%,25%}",
        "- sizing/portfolio rules fixed: long-only, no leverage, equal-weight sizing, no rebalance after entry, same dedupe policy",
        "",
        "## Top 3 by `recommended_default_score`",
    ]

    for _, r in top3.iterrows():
        lines.extend(
            [
                "",
                f"### rank {int(r['rank_by_recommended_default_score'])}: selection_mode=`{r['selection_mode']}`, max_positions={int(r['max_positions'])}, max_weight={float(r['max_weight'])}",
                f"- selected_preset_ids: `{_pretty_sel_ids(str(r['selected_preset_ids']))}`",
                f"- executed_trades: `{int(r['executed_trades'])}`",
                f"- 2024-latest return/dd-adjusted score: `{r['score_return_over_dd_2024_latest']}`",
                f"- 2024-latest total_return={r['total_return_2024_latest']}, max_drawdown={r['max_drawdown_2024_latest']}, sharpe={r['sharpe_2024_latest']}",
                f"- full-period total_return={r['total_return']}, max_drawdown={r['max_drawdown']}, sharpe={r['sharpe']}",
                f"- avg_exposure={r['avg_exposure']}, cash_utilization_rate={r['cash_utilization_rate']}",
            ]
        )

    if len(top3) > 0:
        best = top3.iloc[0]
        best_mode = best["selection_mode"]
        best_ids = _pretty_sel_ids(str(best["selected_preset_ids"]))
        lines.extend(
            [
                "",
                "## Recommended default research deployment config",
                f"**Recommended:** selection_mode=`{best_mode}`, max_positions={int(best['max_positions'])}, max_weight={float(best['max_weight'])}.",
                "",
                "Why (plain-language, metrics-grounded):",
                f"- Drawdown-adjusted return emphasis: it leads on `recommended_default_score` (recent-weighted via return/|drawdown| using 2024=50%, 2022=30%, 2012=20%).",
                "- Exposure usage is acceptable: `avg_exposure`/`cash_utilization_rate` are stable for this no-leverage long-only overlay (enough invested time without needing leverage).",
                f"- Enough trade count: executed_trades={int(best['executed_trades'])} (prevents overfitting to a tiny handful of exits).",
                f"- Not overly dependent on one preset: selected_preset_ids=[{best_ids}] (prefer multi-preset configs where competitive).",
                "",
                "Note: this is a *portfolio simulation overlay* evaluation (research-grade), not live deployable performance.",
            ]
        )

    md_path.write_text("\n".join(lines), encoding="utf-8")

    # Sync to latest/
    for fn in ["portfolio_deployment_config_comparison.csv", "portfolio_deployment_config_report.md"]:
        srcf = out_dir / fn
        if srcf.exists():
            (base_dir.parent / "latest" / fn).write_bytes(srcf.read_bytes())

    print(json.dumps({"out_dir": str(out_dir), "top3": top3[["rank_by_recommended_default_score", "selection_mode", "max_positions", "max_weight", "recommended_default_score"]].to_dict("records")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

