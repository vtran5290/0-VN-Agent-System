from __future__ import annotations

import json
import math
import sys
from itertools import product
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
for p in (ROOT, SRC):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from run import load_curated_data, run_one
from metrics import trade_metrics, trades_per_year, minervini_r_metrics

BASE_CFG = {
    "name": "risk_refine",
    "description": "risk refine around best Wyckoff setup",
    "logic_gate": "Sequential_Event_Validation",
    "setup": "wyckoff",
    "wyckoff_trend_filter": True,
    "trigger_jac_ok": True,
    "sc_vol_mult": 2.5,
    "sc_spread_atr_mult": 1.8,
    "require_tight_base": True,
    "tight_close_window": 8,
    "base_max_close_range_pct": 0.07,
    "base_max_close_stdev_pct": 0.020,
    "require_ultra_dry_days": 1,
    "ultra_dry_vol_ratio": 0.5,
    "require_sos": True,
    "sos_lookback": 10,
    "sos_vol_mult": 1.15,
    "sos_spread_atr_mult": 1.05,
    "min_sos_bars": 1,
    "jac_vol_mult": 1.35,
    "jac_breakout_pct": 0.002,
    "jac_close_pos_min": 0.72,
    "constraints": {"min_tr_duration": 18, "max_tr_volatility": 0.24},
    "fee_bps": 20,
    "slippage_bps": 5,
    "min_hold_bars": 0,
    "warmup_bars": 300,
}


def load_symbols(path: Path) -> list[str]:
    return [
        line.strip().upper()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def score_row(row: dict) -> float:
    pf = row.get("profit_factor")
    exp = row.get("expectancy")
    trades = row.get("trades") or 0
    exp_r = row.get("expectancy_r")
    cagr = row.get("cagr")
    if any(v is None or (isinstance(v, float) and math.isnan(v)) for v in (pf, exp, exp_r, cagr)):
        return -999.0
    if trades < 35:
        return -100.0 + trades / 100.0
    return float(exp * 100 + max(pf - 1.0, 0) * 5 + exp_r + cagr * 2 + math.log(max(trades, 1), 10))


def main() -> int:
    symbols = load_symbols(ROOT.parent / "config" / "watchlist_80.txt")[:80]
    data = load_curated_data(symbols)
    rows = []
    combos = list(product([0.035, 0.04, 0.045], [1.6, 1.8, 2.0], [2, 3, 4]))
    for idx, (stop_pct, atr_k, fail_fast_days) in enumerate(combos, start=1):
        cfg = dict(BASE_CFG)
        cfg["stop_pct"] = stop_pct
        cfg["atr_k"] = atr_k
        cfg["risk_pct"] = 0.006
        cfg["exits"] = {
            "hard_stop": True,
            "trend_break_ma": 50,
            "fail_fast_days": fail_fast_days,
            "climax_proxy": True,
        }
        _, ledger_df = run_one("W2_absorption_breakout_v1", data, cfg_override=cfg)
        m = trade_metrics(ledger_df)
        r = minervini_r_metrics(ledger_df)
        row = {
            "stop_pct": stop_pct,
            "atr_k": atr_k,
            "fail_fast_days": fail_fast_days,
            **m,
            "trades_per_year": trades_per_year(ledger_df),
            **r,
        }
        row["score"] = score_row(row)
        rows.append(row)
        print(f"[{idx:02d}/{len(combos)}] trades={row['trades']} exp={row['expectancy']:.4f} pf={row['profit_factor']:.2f} score={row['score']:.3f} stop={stop_pct} atr={atr_k} ff={fail_fast_days}", flush=True)
    out_df = pd.DataFrame(rows).sort_values(["score", "expectancy", "profit_factor", "trades"], ascending=False)
    out_dir = ROOT / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out_dir / "wyckoff_risk_refine_watchlist80.csv", index=False)
    (out_dir / "wyckoff_risk_refine_watchlist80_top10.json").write_text(json.dumps(out_df.head(10).to_dict(orient="records"), indent=2), encoding="utf-8")
    print(out_df.head(10).to_string(index=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
