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


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_ROOT = Path(__file__).resolve().parents[0]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from minervini_backtest.scripts.run_prebreakout_portfolio_overlay import (  # type: ignore
    PRE_ROOT,
    LATEST,
    PortfolioCfg,
    _load_price_cache,
    _mk_price_lookup,
    _prepare_trade_pool,
    _preset_rank_map,
    _simulate_portfolio,
)
from run import load_curated_data  # noqa: F401


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _parse_ids(raw: Any) -> list[str]:
    if raw is None or (isinstance(raw, float) and np.isnan(raw)):
        return []
    s = str(raw).strip()
    if not s:
        return []
    try:
        parsed = json.loads(s)
        if isinstance(parsed, list):
            return [str(x) for x in parsed]
    except Exception:
        pass
    # fallback: comma-separated string like "P07, P01"
    return [p.strip().strip("`").upper() for p in s.replace("[", "").replace("]", "").replace("'", "").split(",") if p.strip()]


def _compute_pre_pool_size(trade_log: pd.DataFrame, preset_ids: list[str]) -> tuple[int, pd.DataFrame]:
    if trade_log.empty or not preset_ids:
        return 0, pd.DataFrame()
    t = trade_log.copy()
    for c in ["entry_date", "exit_date"]:
        t[c] = pd.to_datetime(t[c], errors="coerce")
    t = t.dropna(subset=["entry_date", "exit_date"])
    t = t[t["preset_id"].astype(str).isin([str(x) for x in preset_ids])].copy()
    return int(len(t)), t


def _daily_bind_series(eq_df: pd.DataFrame, daily_wcb: pd.DataFrame | None) -> np.ndarray:
    # daily_wcb may be sparse; default missing => False.
    dates = eq_df["date"].astype(str).values
    if daily_wcb is None or daily_wcb.empty:
        return np.zeros(len(dates), dtype=bool)
    d = {}
    for _, r in daily_wcb.iterrows():
        d[str(pd.Timestamp(r["date"]).date())] = bool(r["weight_cap_binding"])
    return np.array([d.get(str(pd.Timestamp(x).date()), False) for x in dates], dtype=bool)


def main() -> int:
    ap = argparse.ArgumentParser(description="Portfolio constraint binding diagnostics for deployment configs.")
    ap.add_argument(
        "--prebreakout-dir",
        default=str(LATEST),
        help="Path to `prebreakout_research/latest` (default).",
    )
    args = ap.parse_args()

    base_dir = Path(args.prebreakout_dir)
    comp_csv = base_dir / "portfolio_deployment_config_comparison.csv"
    trade_log_path = base_dir / "trade_log_best_presets.csv"
    robustness_path = base_dir / "preset_robustness_summary.csv"
    oos_path = base_dir / "oos_rolling_train_test_results.csv"

    comp_df = _read_csv(comp_csv)
    trade_log = _read_csv(trade_log_path)
    robustness = _read_csv(robustness_path)
    # oos exists but unused: selected_preset_ids is taken from comparison artifact.
    _ = _read_csv(oos_path)

    if comp_df.empty or trade_log.empty or robustness.empty:
        print("[ERROR] Missing inputs: comparison csv or trade_log or robustness.")
        return 1

    rank_map = _preset_rank_map(robustness)

    dedupe_days = 3
    heat_cap = 0.10
    initial_capital = 1_000_000_000.0
    cost_mult = 1.0
    sizing_mode = "equal_weight"

    # Cache pools and price lookups by exact preset basket.
    cache: dict[str, dict[str, Any]] = {}

    out_rows: list[dict[str, Any]] = []

    for _, r in comp_df.iterrows():
        selection_mode = str(r["selection_mode"])
        selected_preset_ids = _parse_ids(r["selected_preset_ids"])
        max_positions = int(r["max_positions"])
        max_weight = float(r["max_weight"])

        ids_key = ",".join(selected_preset_ids)
        if ids_key not in cache:
            pre_pool_size, _pre_pool = _compute_pre_pool_size(trade_log, selected_preset_ids)
            pool, skipped_dups = _prepare_trade_pool(trade_log, selected_preset_ids, rank_map, dedupe_days)
            symbols = sorted(pool["symbol"].astype(str).unique().tolist()) if not pool.empty else []
            px = _load_price_cache(symbols)
            px_lookup = _mk_price_lookup(px) if symbols else {}
            # skipped_dups is the duplicate_trade pre-dedupe block.
            pre_dedupe_duplicates = int(len(skipped_dups)) if not skipped_dups.empty else 0
            cache[ids_key] = {
                "pre_pool_size": pre_pool_size,
                "pool": pool,
                "skipped_dups": skipped_dups,
                "px_lookup": px_lookup,
                "pre_dedupe_duplicates": pre_dedupe_duplicates,
            }

        entry = cache[ids_key]
        pre_pool_size = int(entry["pre_pool_size"])
        pool = entry["pool"]
        skipped_dups = entry["skipped_dups"]
        px_lookup = entry["px_lookup"]
        pre_dedupe_duplicates = int(entry["pre_dedupe_duplicates"])

        cfg = PortfolioCfg(
            initial_capital=initial_capital,
            max_positions=max_positions,
            max_weight=max_weight,
            heat_cap=heat_cap,
            no_rebalance_after_entry=True,
            sizing_mode=sizing_mode,
            dedupe_days=dedupe_days,
            additional_cost_mult=cost_mult,
        )

        if pool.empty or pre_pool_size == 0:
            out_rows.append(
                {
                    "selection_mode": selection_mode,
                    "selected_preset_ids": json.dumps(selected_preset_ids),
                    "max_positions": max_positions,
                    "max_weight": max_weight,
                    "executed_trades": 0,
                    "avg_open_positions": np.nan,
                    "median_open_positions": np.nan,
                    "max_open_positions_observed": 0,
                    "pct_days_at_max_positions": np.nan,
                    "avg_realized_position_weight_on_entry": np.nan,
                    "max_realized_position_weight_on_entry": np.nan,
                    "pct_entries_blocked_max_positions": np.nan,
                    "pct_entries_blocked_max_weight": np.nan,
                    "pct_entries_blocked_heat_cap": np.nan,
                    "pct_entries_blocked_insufficient_cash": np.nan,
                    "pct_entries_blocked_duplicate_trade": np.nan,
                    "pct_days_weight_cap_binding": np.nan,
                    "pct_days_cash_greater_than_50pct": np.nan,
                    "avg_cash_pct": np.nan,
                    "avg_market_value_pct": np.nan,
                }
            )
            continue

        pool2 = pool.copy()
        pool2["selection_mode"] = selection_mode

        eq_df, trade_df, _skipped, diag = _simulate_portfolio(pool2, px_lookup, cfg, skipped_dups, diagnostics=True)
        if eq_df.empty or trade_df is None:
            out_rows.append(
                {
                    "selection_mode": selection_mode,
                    "selected_preset_ids": json.dumps(selected_preset_ids),
                    "max_positions": max_positions,
                    "max_weight": max_weight,
                    "executed_trades": 0,
                    "avg_open_positions": np.nan,
                    "median_open_positions": np.nan,
                    "max_open_positions_observed": 0,
                    "pct_days_at_max_positions": np.nan,
                    "avg_realized_position_weight_on_entry": np.nan,
                    "max_realized_position_weight_on_entry": np.nan,
                    "pct_entries_blocked_max_positions": np.nan,
                    "pct_entries_blocked_max_weight": np.nan,
                    "pct_entries_blocked_heat_cap": np.nan,
                    "pct_entries_blocked_insufficient_cash": np.nan,
                    "pct_entries_blocked_duplicate_trade": np.nan,
                    "pct_days_weight_cap_binding": np.nan,
                    "pct_days_cash_greater_than_50pct": np.nan,
                    "avg_cash_pct": np.nan,
                    "avg_market_value_pct": np.nan,
                }
            )
            continue

        entry_attempts = diag.get("entry_attempts")
        daily_wcb = diag.get("daily_weight_cap_binding")

        # Daily stats
        cash_pct = (eq_df["cash"].astype(float) / eq_df["equity"].astype(float).replace(0.0, np.nan)).replace([np.inf, -np.inf], np.nan)
        mv_pct = (eq_df["market_value"].astype(float) / eq_df["equity"].astype(float).replace(0.0, np.nan)).replace([np.inf, -np.inf], np.nan)
        dates = eq_df["date"].astype(str)

        wcb_series = _daily_bind_series(eq_df, daily_wcb)
        pct_days_weight_cap_binding = float(np.mean(wcb_series)) if len(wcb_series) else np.nan

        open_pos_series = eq_df["open_positions"].astype(float).values
        avg_open_positions = float(np.nanmean(open_pos_series)) if len(open_pos_series) else np.nan
        median_open_positions = float(np.nanmedian(open_pos_series)) if len(open_pos_series) else np.nan
        max_open_positions_observed = int(np.nanmax(open_pos_series)) if len(open_pos_series) else 0
        pct_days_at_max_positions = float(np.mean(open_pos_series == float(max_positions))) if len(open_pos_series) else np.nan

        # Entry stats: realized weights and skip reasons.
        executed_attempts = entry_attempts[entry_attempts.get("executed", False) == True] if not entry_attempts.empty else pd.DataFrame()
        avg_realized_weight = float(executed_attempts["realized_position_weight_on_entry"].astype(float).mean()) if not executed_attempts.empty else np.nan
        max_realized_weight = float(executed_attempts["realized_position_weight_on_entry"].astype(float).max()) if not executed_attempts.empty else np.nan

        total_attempts_deduped = int(len(entry_attempts)) if not entry_attempts.empty else 0

        def _count_skip(reason: str) -> int:
            if entry_attempts is None or entry_attempts.empty:
                return 0
            return int(((entry_attempts["executed"] == False) & (entry_attempts["skip_reason"].astype(str) == reason)).sum())

        blocked_max_positions = _count_skip("max_positions_reached")
        blocked_heat_cap = _count_skip("heat_cap_reached")
        blocked_insufficient_cash = _count_skip("insufficient_cash")
        blocked_duplicate_trade_sim = _count_skip("duplicate_trade")

        # Weight cap binding entries (executed only).
        weight_cap_bind_entries = 0
        if not entry_attempts.empty and "weight_cap_binding_for_entry" in entry_attempts.columns:
            weight_cap_bind_entries = int(
                ((entry_attempts["executed"] == True) & (entry_attempts["weight_cap_binding_for_entry"] == True)).sum()
            )

        pct_entries_blocked_max_positions = blocked_max_positions / pre_pool_size
        pct_entries_blocked_heat_cap = blocked_heat_cap / pre_pool_size
        pct_entries_blocked_insufficient_cash = blocked_insufficient_cash / pre_pool_size

        # "duplicate_trade" includes both pre-dedupe duplicates and in-simulation already-open duplicates.
        duplicates_total = pre_dedupe_duplicates + blocked_duplicate_trade_sim
        pct_entries_blocked_duplicate_trade = duplicates_total / pre_pool_size

        pct_entries_blocked_max_weight = weight_cap_bind_entries / pre_pool_size

        pct_days_cash_greater_than_50pct = float(np.nanmean((cash_pct > 0.5).astype(float))) if len(cash_pct) else np.nan
        avg_cash_pct = float(np.nanmean(cash_pct)) if len(cash_pct) else np.nan
        avg_market_value_pct = float(np.nanmean(mv_pct)) if len(mv_pct) else np.nan

        out_rows.append(
            {
                "selection_mode": selection_mode,
                "selected_preset_ids": json.dumps(selected_preset_ids),
                "max_positions": max_positions,
                "max_weight": max_weight,
                "executed_trades": int(len(trade_df)),
                "avg_open_positions": avg_open_positions,
                "median_open_positions": median_open_positions,
                "max_open_positions_observed": max_open_positions_observed,
                "pct_days_at_max_positions": pct_days_at_max_positions,
                "avg_realized_position_weight_on_entry": avg_realized_weight,
                "max_realized_position_weight_on_entry": max_realized_weight,
                "pct_entries_blocked_max_positions": pct_entries_blocked_max_positions,
                "pct_entries_blocked_max_weight": pct_entries_blocked_max_weight,
                "pct_entries_blocked_heat_cap": pct_entries_blocked_heat_cap,
                "pct_entries_blocked_insufficient_cash": pct_entries_blocked_insufficient_cash,
                "pct_entries_blocked_duplicate_trade": pct_entries_blocked_duplicate_trade,
                "pct_days_weight_cap_binding": pct_days_weight_cap_binding,
                "pct_days_cash_greater_than_50pct": pct_days_cash_greater_than_50pct,
                "avg_cash_pct": avg_cash_pct,
                "avg_market_value_pct": avg_market_value_pct,
            }
        )

    out_df = pd.DataFrame(out_rows)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = PRE_ROOT / f"portfolio_constraint_binding_diagnostics_{ts}"
    run_dir.mkdir(parents=True, exist_ok=True)

    out_csv = run_dir / "portfolio_constraint_binding_diagnostics.csv"
    out_md = run_dir / "portfolio_constraint_binding_diagnostics.md"
    out_df.to_csv(out_csv, index=False)

    # Build compact narrative for binding drivers (computed from top config rows).
    # We will compare the highest-ranked configs by recommended_default_score in the comparison csv.
    # However we don't trust that ordering here, so we re-load score and pick top.
    comp_df2 = comp_df.sort_values("recommended_default_score", ascending=False).reset_index(drop=True)
    top_row = comp_df2.iloc[0]
    top2_row = comp_df2.iloc[1] if len(comp_df2) > 1 else None
    top3_row = comp_df2.iloc[2] if len(comp_df2) > 2 else None

    def _find_row_by_ids_set(mode: str, ids: list[str], max_pos: int, max_w: float) -> pd.Series | None:
        # Match by mode + (max_positions, max_weight) and compare preset set ignoring order.
        if out_df.empty:
            return None
        max_w_r = round(float(max_w), 10)
        sel = out_df[
            (out_df["selection_mode"] == mode)
            & (out_df["max_positions"] == int(max_pos))
            & (out_df["max_weight"].astype(float).round(10) == max_w_r)
        ]
        if sel.empty:
            return None
        target_set = set([str(x).upper() for x in ids])
        for _, rr in sel.iterrows():
            rr_ids = _parse_ids(rr.get("selected_preset_ids"))
            if set([str(x).upper() for x in rr_ids]) == target_set:
                return sel.loc[_, :]
        return None

    def _summ_line(rr: pd.Series) -> str:
        return (
            f"selection_mode=`{rr['selection_mode']}`, max_positions={int(rr['max_positions'])}, max_weight={float(rr['max_weight'])}, "
            f"executed_trades={int(rr['executed_trades'])}, pct_days_weight_cap_binding={rr['pct_days_weight_cap_binding']:.6f}, "
            f"pct_entries_blocked_max_positions={rr['pct_entries_blocked_max_positions']:.6f}, "
            f"pct_entries_blocked_insufficient_cash={rr['pct_entries_blocked_insufficient_cash']:.6f}, "
            f"pct_entries_blocked_heat_cap={rr['pct_entries_blocked_heat_cap']:.6f}"
        )

    lines = ["# Portfolio constraint binding diagnostics", ""]
    if len(out_df) == 0:
        lines.append("- No diagnostics rows computed (empty output).")
    else:
        lines.append("- Computed from actual portfolio overlay re-simulation for each deployment config row.")
        lines.append("- Definitions note: `pct_entries_blocked_max_weight` counts executed entries where the realized entry weight was constrained by the `max_weight` cap; it is not a skip reason (weight cap reduces target sizing but may still execute).")
        lines.append("")

        top_rr = _find_row_by_ids_set(
            str(top_row["selection_mode"]),
            _parse_ids(top_row["selected_preset_ids"]),
            int(top_row["max_positions"]),
            float(top_row["max_weight"]),
        )
        top2_rr = None
        top3_rr = None
        if top2_row is not None:
            top2_rr = _find_row_by_ids_set(
                str(top2_row["selection_mode"]),
                _parse_ids(top2_row["selected_preset_ids"]),
                int(top2_row["max_positions"]),
                float(top2_row["max_weight"]),
            )
        if top3_row is not None:
            top3_rr = _find_row_by_ids_set(
                str(top3_row["selection_mode"]),
                _parse_ids(top3_row["selected_preset_ids"]),
                int(top3_row["max_positions"]),
                float(top3_row["max_weight"]),
            )

        if top_rr is not None:
            lines.append("## Binding drivers (top-ranked configs)")
            lines.append(f"- top1: {_summ_line(top_rr)}")
        if top2_rr is not None:
            lines.append(f"- top2: {_summ_line(top2_rr)}")
        if top3_rr is not None:
            lines.append(f"- top3: {_summ_line(top3_rr)}")

        # Task B: explain whether max_weight=25% matters for max_positions=8.
        # Filter out rows where max_positions=8, max_weight=0.25.
        cand_25 = out_df[(out_df["max_positions"] == 8) & (out_df["max_weight"].astype(float) == float(0.25))]
        if len(cand_25) > 0:
            # We'll look at the median weight-cap binding across those rows.
            wcb = float(cand_25["pct_days_weight_cap_binding"].astype(float).mean())
            entries_wcb = float(cand_25["pct_entries_blocked_max_weight"].astype(float).mean())
            lines.append("")
            lines.append("## Did `max_weight=25%` matter when `max_positions=8`?")
            lines.append(f"- Avg `pct_days_weight_cap_binding` across those configs: {wcb:.6f}")
            lines.append(f"- Avg `pct_entries_blocked_max_weight` across those configs: {entries_wcb:.6f}")
            if entries_wcb <= 1e-9 and wcb <= 1e-9:
                lines.append("- Answer: No. In this equal-weight overlay with `max_positions=8`, the per-entry target weight is bounded by `1/max_positions` (12.5%) which is always <= 25%, so the max_weight cap is effectively non-binding.")
            else:
                lines.append("- Answer: Yes, occasionally. Some executed entries still hit weight-cap binding; check the exact row values above.")

        # Task C: explicitly compare best configs for:
        # - latest_robustness_ranked
        # - top_k_presets_union
        lines.append("")
        lines.append("## Was selection_mode actually different?")
        try:
            comp_df3 = comp_df.sort_values("recommended_default_score", ascending=False).reset_index(drop=True)
            best_latest = comp_df3[comp_df3["selection_mode"] == "latest_robustness_ranked"].iloc[0]
            best_topk = comp_df3[comp_df3["selection_mode"] == "top_k_presets_union"].iloc[0]

            latest_diag = _find_row_by_ids_set(
                "latest_robustness_ranked",
                _parse_ids(best_latest["selected_preset_ids"]),
                int(best_latest["max_positions"]),
                float(best_latest["max_weight"]),
            )
            topk_diag = _find_row_by_ids_set(
                "top_k_presets_union",
                _parse_ids(best_topk["selected_preset_ids"]),
                int(best_topk["max_positions"]),
                float(best_topk["max_weight"]),
            )

            if latest_diag is not None and topk_diag is not None:
                latest_ids = _parse_ids(latest_diag.get("selected_preset_ids"))
                topk_ids = _parse_ids(topk_diag.get("selected_preset_ids"))
                same_basket = set([str(x).upper() for x in latest_ids]) == set([str(x).upper() for x in topk_ids])
                same_trade_count = int(latest_diag.get("executed_trades", -1)) == int(topk_diag.get("executed_trades", -1))
                same_binding = (
                    float(latest_diag.get("pct_days_weight_cap_binding", np.nan)) == float(topk_diag.get("pct_days_weight_cap_binding", np.nan))
                    and float(latest_diag.get("pct_entries_blocked_max_positions", np.nan)) == float(topk_diag.get("pct_entries_blocked_max_positions", np.nan))
                )
                lines.append(
                    f"- best latest_robustness_ranked: presets={latest_ids}, max_positions={int(latest_diag.get('max_positions'))}, max_weight={float(latest_diag.get('max_weight'))}, executed_trades={int(latest_diag.get('executed_trades'))}"
                )
                lines.append(
                    f"- best top_k_presets_union: presets={topk_ids}, max_positions={int(topk_diag.get('max_positions'))}, max_weight={float(topk_diag.get('max_weight'))}, executed_trades={int(topk_diag.get('executed_trades'))}"
                )
                if same_basket and same_trade_count and same_binding:
                    lines.append("- Answer: negligible difference in this run; both selection modes effectively execute the same trade pool under the binding constraints.")
                else:
                    lines.append("- Answer: selection_mode changes the effective executed pool or constraint-binding pattern; compare the executed_trades and binding metrics above.")
            else:
                lines.append("- Answer: Unable to locate diagnostics rows for both selection modes; check computed out_df coverage.")
        except Exception:
            lines.append("- Answer: Unknown (failed to compute top-by-mode comparison from comparison csv).")

    out_md.write_text("\n".join(lines), encoding="utf-8")

    # sync to latest/
    latest_csv = base_dir / "portfolio_constraint_binding_diagnostics.csv"
    latest_md = base_dir / "portfolio_constraint_binding_diagnostics.md"
    latest_csv.write_bytes(out_csv.read_bytes())
    latest_md.write_bytes(out_md.read_bytes())

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

