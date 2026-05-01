from __future__ import annotations

"""
Lightweight robustness layer for PP backtests.

Inputs:
- `pp_backtest/pp_trade_ledger.csv` (preferred) or a path via --ledger.

Outputs:
- `artifacts/robustness_pp_{tag}.json`
- `artifacts/robustness_pp_{tag}.md`

This module does not change any strategy signals; it stresses execution/cost assumptions
and bootstraps realized trade returns to estimate drawdown fragility.
"""

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from src.backtest.execution import ExecutionConfig, FillTiming, apply_costs, execution_mode_label


_REPO = Path(__file__).resolve().parent.parent
_PP = Path(__file__).resolve().parent


def _equity_from_trade_returns(rets: np.ndarray, initial: float = 1.0) -> np.ndarray:
    eq = np.empty(len(rets) + 1, dtype=float)
    eq[0] = float(initial)
    for i, r in enumerate(rets, start=1):
        eq[i] = eq[i - 1] * (1.0 + float(r))
    return eq


def _max_drawdown(eq: np.ndarray) -> float:
    if eq.size <= 1:
        return float("nan")
    peak = np.maximum.accumulate(eq)
    dd = eq / peak - 1.0
    return float(np.min(dd))


def _bootstrap_max_dd(rets: np.ndarray, n_sim: int = 1000, seed: int = 42) -> Dict[str, float]:
    if rets.size == 0:
        return {"expected_max_dd": float("nan"), "median_max_dd": float("nan"), "p05_max_dd": float("nan"), "p01_max_dd": float("nan")}
    rng = np.random.default_rng(seed)
    mdds = np.empty(n_sim, dtype=float)
    n = len(rets)
    for i in range(n_sim):
        samp = rng.choice(rets, size=n, replace=True)
        eq = _equity_from_trade_returns(samp)
        mdds[i] = _max_drawdown(eq)
    return {
        "expected_max_dd": float(np.mean(mdds)),
        "median_max_dd": float(np.median(mdds)),
        "p05_max_dd": float(np.percentile(mdds, 5)),
        "p01_max_dd": float(np.percentile(mdds, 1)),
    }


def _summary_metrics(rets: np.ndarray) -> Dict[str, float]:
    if rets.size == 0:
        return {"trades": 0, "avg_ret": float("nan"), "win_rate": float("nan"), "profit_factor": float("nan"), "tail5": float("nan"), "max_drawdown": float("nan")}
    wins = rets[rets > 0]
    losses = rets[rets <= 0]
    pf = (wins.sum() / (-losses.sum())) if losses.size and losses.sum() < 0 and wins.size else float("nan")
    eq = _equity_from_trade_returns(rets)
    return {
        "trades": int(rets.size),
        "avg_ret": float(np.mean(rets)),
        "win_rate": float(np.mean(rets > 0)),
        "profit_factor": float(pf),
        "tail5": float(np.percentile(rets, 5)),
        "max_drawdown": _max_drawdown(eq),
    }


def _recompute_trade_returns_from_raw_prices(
    df: pd.DataFrame,
    exec_cfg: ExecutionConfig,
) -> np.ndarray:
    """
    Recompute trade returns from raw entry/exit open prices stored in the ledger.
    Requires columns: entry_open_raw, exit_open_raw.
    """
    if "entry_open_raw" not in df.columns or "exit_open_raw" not in df.columns:
        raise ValueError("Ledger missing entry_open_raw/exit_open_raw; re-run backtest to generate them.")
    fee = exec_cfg.fee_mult()
    slip = exec_cfg.slip_mult()
    entry = df["entry_open_raw"].astype(float).values
    exit_ = df["exit_open_raw"].astype(float).values
    buy_px = np.array([apply_costs(px, "buy", fee, slip) for px in entry], dtype=float)
    sell_px = np.array([apply_costs(px, "sell", fee, slip) for px in exit_], dtype=float)
    return (sell_px / buy_px) - 1.0


@dataclass(frozen=True)
class RobustnessCase:
    name: str
    exec_mode: str
    metrics: Dict[str, float]
    bootstrap_dd: Dict[str, float]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", default=str(_PP / "pp_trade_ledger.csv"), help="Path to pp_trade_ledger.csv")
    ap.add_argument("--tag", default="latest", help="Output tag for artifacts")
    ap.add_argument("--n-sim", type=int, default=1000, help="Bootstrap simulations")
    args = ap.parse_args()

    ledger_path = Path(args.ledger)
    if not ledger_path.is_absolute():
        ledger_path = _REPO / ledger_path
    if not ledger_path.exists():
        raise SystemExit(f"Ledger not found: {ledger_path}")

    df = pd.read_csv(ledger_path)
    df = df[df.get("ret").notna()] if "ret" in df.columns else df

    base_fee = float(df["fee_bps_per_side"].iloc[0]) if "fee_bps_per_side" in df.columns and len(df) else 15.0
    base_slip = float(df["slippage_bps_per_side"].iloc[0]) if "slippage_bps_per_side" in df.columns and len(df) else 5.0

    cases: List[Tuple[str, float, float]] = [
        ("base", 1.0, 1.0),
        ("cost_1p5x", 1.5, 1.5),
        ("cost_2x", 2.0, 2.0),
    ]
    out_cases: List[RobustnessCase] = []

    for name, m_fee, m_slip in cases:
        exec_cfg = ExecutionConfig(
            entry_timing=FillTiming.NEXT_BAR_OPEN,
            exit_timing=FillTiming.NEXT_BAR_OPEN,
            fee_bps_per_side=base_fee * m_fee,
            slippage_bps_per_side=base_slip * m_slip,
        )
        rets = _recompute_trade_returns_from_raw_prices(df, exec_cfg)
        out_cases.append(
            RobustnessCase(
                name=name,
                exec_mode=execution_mode_label(exec_cfg),
                metrics=_summary_metrics(rets),
                bootstrap_dd=_bootstrap_max_dd(rets, n_sim=int(args.n_sim)),
            )
        )

    out_dir = _REPO / "artifacts"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_json = out_dir / f"robustness_pp_{args.tag}.json"
    out_md = out_dir / f"robustness_pp_{args.tag}.md"

    payload = {
        "ledger": str(ledger_path),
        "cases": [asdict(c) for c in out_cases],
        "notes": "Returns recomputed from raw open prices with stressed fee/slippage; signals unchanged. Bootstrap resamples trade returns (IID assumption).",
    }
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = []
    lines.append("# Robustness Report (PP)\n\n")
    lines.append(f"- **ledger**: `{ledger_path}`\n")
    lines.append(f"- **n_sim**: {int(args.n_sim)}\n\n")
    lines.append("## Results\n\n")
    for c in out_cases:
        m = c.metrics
        b = c.bootstrap_dd
        lines.append(f"### {c.name}\n")
        lines.append(f"- **execution**: {c.exec_mode}\n")
        lines.append(f"- **trades**: {m.get('trades')}\n")
        lines.append(f"- **avg_ret**: {m.get('avg_ret'):.4f}\n" if m.get("avg_ret") == m.get("avg_ret") else "- **avg_ret**: nan\n")
        lines.append(f"- **win_rate**: {m.get('win_rate'):.3f}\n" if m.get("win_rate") == m.get("win_rate") else "- **win_rate**: nan\n")
        lines.append(f"- **profit_factor**: {m.get('profit_factor'):.3f}\n" if m.get("profit_factor") == m.get("profit_factor") else "- **profit_factor**: nan\n")
        lines.append(f"- **tail5**: {m.get('tail5'):.3f}\n" if m.get("tail5") == m.get("tail5") else "- **tail5**: nan\n")
        lines.append(f"- **max_drawdown (trade-equity)**: {m.get('max_drawdown'):.3f}\n" if m.get("max_drawdown") == m.get("max_drawdown") else "- **max_drawdown**: nan\n")
        lines.append(f"- **bootstrap expected_max_dd**: {b.get('expected_max_dd'):.3f}\n" if b.get("expected_max_dd") == b.get("expected_max_dd") else "- **bootstrap expected_max_dd**: nan\n")
        lines.append(f"- **bootstrap p05_max_dd**: {b.get('p05_max_dd'):.3f}\n" if b.get("p05_max_dd") == b.get("p05_max_dd") else "- **bootstrap p05_max_dd**: nan\n")
        lines.append(f"- **bootstrap p01_max_dd**: {b.get('p01_max_dd'):.3f}\n\n" if b.get("p01_max_dd") == b.get("p01_max_dd") else "- **bootstrap p01_max_dd**: nan\n\n")

    out_md.write_text("".join(lines), encoding="utf-8")
    print(f"[robustness] wrote {out_json}")
    print(f"[robustness] wrote {out_md}")


if __name__ == "__main__":
    main()

