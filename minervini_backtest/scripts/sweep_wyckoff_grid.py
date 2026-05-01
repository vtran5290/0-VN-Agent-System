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


def load_symbols(path: Path) -> list[str]:
    return [
        line.strip().upper()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def build_cfg(name: str, tight_mode: str, dry_days: int, sos_mode: str, jump_mode: str, cause_mode: str) -> dict:
    cfg = {
        "name": name,
        "description": f"tight={tight_mode}, dry={dry_days}, sos={sos_mode}, jump={jump_mode}, cause={cause_mode}",
        "logic_gate": "Sequential_Event_Validation",
        "setup": "wyckoff",
        "wyckoff_trend_filter": True,
        "trigger_jac_ok": True,
        "sc_vol_mult": 2.5,
        "sc_spread_atr_mult": 1.8,
        "stop_pct": 0.04,
        "atr_k": 1.8,
        "risk_pct": 0.006,
        "exits": {
            "hard_stop": True,
            "trend_break_ma": 50,
            "fail_fast_days": 3,
            "climax_proxy": True,
        },
        "fee_bps": 20,
        "slippage_bps": 5,
        "min_hold_bars": 0,
        "warmup_bars": 300,
    }

    if cause_mode == "loose":
        cfg["constraints"] = {"min_tr_duration": 18, "max_tr_volatility": 0.24}
    else:
        cfg["constraints"] = {"min_tr_duration": 22, "max_tr_volatility": 0.22}

    if tight_mode == "off":
        cfg["require_tight_base"] = False
    else:
        cfg.update(
            {
                "require_tight_base": True,
                "tight_close_window": 8,
                "base_max_close_range_pct": 0.07 if tight_mode == "moderate" else 0.06,
                "base_max_close_stdev_pct": 0.020 if tight_mode == "moderate" else 0.017,
            }
        )

    if dry_days > 0:
        cfg["require_ultra_dry_days"] = dry_days
        cfg["ultra_dry_vol_ratio"] = 0.50 if dry_days == 1 else 0.45

    if sos_mode == "one":
        cfg.update(
            {
                "require_sos": True,
                "sos_lookback": 10,
                "sos_vol_mult": 1.15,
                "sos_spread_atr_mult": 1.05,
                "min_sos_bars": 1,
            }
        )
    elif sos_mode == "two":
        cfg.update(
            {
                "require_sos": True,
                "sos_lookback": 12,
                "sos_vol_mult": 1.20,
                "sos_spread_atr_mult": 1.10,
                "min_sos_bars": 2,
            }
        )

    if jump_mode == "base":
        cfg.update({"jac_vol_mult": 1.25, "jac_breakout_pct": 0.001, "jac_close_pos_min": 0.68})
    else:
        cfg.update({"jac_vol_mult": 1.35, "jac_breakout_pct": 0.002, "jac_close_pos_min": 0.72})

    return cfg


def score_row(row: dict) -> float:
    pf = row.get("profit_factor")
    exp = row.get("expectancy")
    trades = row.get("trades") or 0
    exp_r = row.get("expectancy_r")
    cagr = row.get("cagr")
    if any(v is None or (isinstance(v, float) and math.isnan(v)) for v in (pf, exp, exp_r, cagr)):
        return -999.0
    if trades < 40:
        return -100.0 + trades / 100.0
    return float(exp * 100 + max(pf - 1.0, 0) * 5 + exp_r + cagr * 2 + math.log(max(trades, 1), 10))


def main() -> int:
    watchlist_path = ROOT.parent / "config" / "watchlist_80.txt"
    symbols = load_symbols(watchlist_path)[:80]
    data = load_curated_data(symbols)
    if not data:
        raise RuntimeError("No data loaded for watchlist_80.")

    out_rows: list[dict] = []
    combos = list(product(
        ["off", "moderate"],
        [0, 1],
        ["off", "one"],
        ["base", "strong"],
        ["loose", "std"],
    )) + [("moderate", 1, "two", "strong", "std")]

    for idx, (tight_mode, dry_days, sos_mode, jump_mode, cause_mode) in enumerate(combos, start=1):
        name = f"grid_{idx:02d}"
        cfg = build_cfg(name, tight_mode, dry_days, sos_mode, jump_mode, cause_mode)
        _, ledger_df = run_one("W2_loose_sc_trend", data, cfg_override=cfg)
        metrics = trade_metrics(ledger_df)
        r_metrics = minervini_r_metrics(ledger_df)
        row = {
            "config_name": name,
            "tight_mode": tight_mode,
            "dry_days": dry_days,
            "sos_mode": sos_mode,
            "jump_mode": jump_mode,
            "cause_mode": cause_mode,
            **metrics,
            "trades_per_year": trades_per_year(ledger_df),
            **r_metrics,
        }
        row["score"] = score_row(row)
        out_rows.append(row)
        print(
            f"[{idx:02d}/{len(combos)}] trades={row['trades']} exp={row['expectancy']:.4f} pf={row['profit_factor']:.2f} "
            f"score={row['score']:.3f} tight={tight_mode} dry={dry_days} sos={sos_mode} jump={jump_mode} cause={cause_mode}",
            flush=True,
        )

    out_df = pd.DataFrame(out_rows).sort_values(["score", "expectancy", "profit_factor", "trades"], ascending=False)
    out_dir = ROOT / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "wyckoff_grid_watchlist80.csv"
    json_path = out_dir / "wyckoff_grid_watchlist80_top10.json"
    out_df.to_csv(csv_path, index=False)
    top10 = out_df.head(10).to_dict(orient="records")
    json_path.write_text(json.dumps(top10, indent=2), encoding="utf-8")
    print(f"Saved full grid to {csv_path}")
    print(f"Saved top 10 to {json_path}")
    print(out_df.head(10).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
