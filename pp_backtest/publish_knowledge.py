# pp_backtest/publish_knowledge.py — Pack backtest results into Knowledge Store (per symbol, per strategy)
"""
Run after backtest + pivot. Builds self-contained JSON records and updates index.
Usage: python -m pp_backtest.publish_knowledge --strategy PP_GIL_V4 [--symbols MBB SSI ...] [--start 2018-01-01] [--end 2026-02-21]
If --symbols omitted, uses all symbols from results CSV.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

_REPO = Path(__file__).resolve().parent.parent
_PP = Path(__file__).resolve().parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

KNOWLEDGE_BACKTESTS = _REPO / "knowledge" / "backtests"
INDEX_PATH = _REPO / "knowledge" / "backtests" / "index.json"
RESULTS_CSV = _PP / "pp_sell_backtest_results.csv"
LEDGER_CSV = _PP / "pp_trade_ledger.csv"
PRESETS_PATH = _PP / "presets.yml"


def _load_preset(strategy_id: str) -> dict:
    try:
        import yaml
    except ImportError:
        return {"id": strategy_id, "version": "1.0.0"}
    if not PRESETS_PATH.exists():
        return {"id": strategy_id, "version": "1.0.0"}
    with open(PRESETS_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    presets = data.get("presets", {})
    return presets.get(strategy_id, {"id": strategy_id, "version": "1.0.0"})


def _params_hash(preset: dict, date_range: dict, data_source: str) -> str:
    blob = json.dumps({
        "preset": preset,
        "date_range": date_range,
        "data_source": data_source,
    }, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()[:12]


def _exit_reason_breakdown(ledger: pd.DataFrame, symbol: str) -> dict:
    sub = ledger[ledger["symbol"] == symbol]
    if sub.empty:
        return {}
    out = {}
    for reason in ["SELL_V4", "MARKET_DD", "STOCK_DD", "EOD_FORCE"]:
        r = sub[sub["exit_reason"] == reason]
        if r.empty:
            continue
        out[reason] = {
            "count": int(len(r)),
            "win_rate": float((r["ret"] > 0).mean()),
            "avg_ret": float(r["ret"].mean()),
        }
        if "mfe_pct" in r.columns and r["mfe_pct"].notna().any():
            out[reason]["mfe_20_avg"] = float(r["mfe_pct"].mean())
    return out


def build_record(
    symbol: str,
    strategy_id: str,
    stats_row: dict,
    ledger: pd.DataFrame,
    date_range: dict,
    data_source: str,
    preset: dict,
    params_hash_val: str,
    results_mtime: str | None = None,
    ledger_mtime: str | None = None,
) -> dict:
    generated_at = datetime.now(timezone.utc).isoformat()
    exit_breakdown = _exit_reason_breakdown(ledger, symbol)
    inputs = {}
    if results_mtime is not None:
        inputs["results_csv_mtime"] = results_mtime
    if ledger_mtime is not None:
        inputs["ledger_csv_mtime"] = ledger_mtime
    return {
        "symbol": symbol,
        "strategy_id": strategy_id,
        "data_source": data_source,
        "date_range": date_range,
        "execution": {
            "entry": "next_open",
            "exit": "next_open",
            "fee_bps": 15,
            "slippage_bps": 5,
        },
        "params_hash": params_hash_val,
        "generated_at": generated_at,
        "inputs": inputs,
        "stats": {
            "trades": int(stats_row.get("trades", 0)),
            "win_rate": float(stats_row.get("win_rate", 0)),
            "avg_ret": float(stats_row.get("avg_ret", 0)),
            "median_ret": float(stats_row.get("median_ret", 0)),
            "avg_win": float(stats_row.get("avg_win", 0)) if pd.notna(stats_row.get("avg_win")) else None,
            "avg_loss": float(stats_row.get("avg_loss", 0)) if pd.notna(stats_row.get("avg_loss")) else None,
            "profit_factor": float(stats_row.get("profit_factor", 0)) if pd.notna(stats_row.get("profit_factor")) else None,
            "max_drawdown": float(stats_row.get("max_drawdown", 0)) if pd.notna(stats_row.get("max_drawdown")) else None,
            "avg_hold_days": float(stats_row.get("avg_hold_days", 0)) if pd.notna(stats_row.get("avg_hold_days")) else None,
        },
        "exit_reason_breakdown": exit_breakdown,
        "validity": {
            "regime_tags": ["risk_on", "neutral"],
            "market_condition_notes": "Works best when VN30 DD/20 < 6 and leaders hold MA20.",
            "relevance_score": 0.7,
            "warnings": [],
        },
        "build": {
            "params_hash": params_hash_val,
            "code_version": "git:na",
            "preset_version": preset.get("version", "1.0.0"),
        },
        "notes": [],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strategy", default="PP_GIL_V4", help="Preset strategy id")
    ap.add_argument("--symbols", nargs="*", help="Symbols to publish (default: all from results)")
    ap.add_argument("--start", default="2018-01-01")
    ap.add_argument("--end", default="2026-02-21")
    ap.add_argument("--data-source", default="fireant_historical")
    ap.add_argument("--results", default=str(RESULTS_CSV))
    ap.add_argument("--ledger", default=str(LEDGER_CSV))
    args = ap.parse_args()

    if not Path(args.results).exists():
        print(f"Results not found: {args.results}. Run backtest first.")
        return 1
    results_df = pd.read_csv(args.results)
    ledger_df = pd.read_csv(args.ledger) if Path(args.ledger).exists() else pd.DataFrame()

    symbols = args.symbols or list(results_df["symbol"].astype(str).unique())
    date_range = {"start": args.start, "end": args.end}
    preset = _load_preset(args.strategy)
    params_hash_val = _params_hash(preset, date_range, args.data_source)

    KNOWLEDGE_BACKTESTS.mkdir(parents=True, exist_ok=True)
    index = {"updated_at": datetime.now(timezone.utc).isoformat(), "latest": {}}

    if INDEX_PATH.exists():
        index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        index["updated_at"] = datetime.now(timezone.utc).isoformat()
    if "latest" not in index:
        index["latest"] = {}

    results_path = Path(args.results)
    ledger_path = Path(args.ledger)
    results_mtime = datetime.fromtimestamp(results_path.stat().st_mtime, tz=timezone.utc).isoformat() if results_path.exists() else None
    ledger_mtime = datetime.fromtimestamp(ledger_path.stat().st_mtime, tz=timezone.utc).isoformat() if ledger_path.exists() else None

    for sym in symbols:
        row = results_df[results_df["symbol"] == sym]
        if row.empty:
            continue
        stats_row = row.iloc[0].to_dict()
        rec = build_record(
            sym, args.strategy, stats_row, ledger_df, date_range, args.data_source, preset, params_hash_val,
            results_mtime=results_mtime, ledger_mtime=ledger_mtime,
        )
        sym_dir = KNOWLEDGE_BACKTESTS / sym
        sym_dir.mkdir(parents=True, exist_ok=True)
        out_path = sym_dir / f"{args.strategy}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(rec, f, ensure_ascii=False, indent=2)
        rel = str(out_path.relative_to(_REPO)).replace("\\", "/")
        index.setdefault("latest", {}).setdefault(sym, {})[args.strategy] = rel

    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print(f"Published {len(symbols)} records to knowledge/backtests/; index updated.")
    return 0


if __name__ == "__main__":
    exit(main())
