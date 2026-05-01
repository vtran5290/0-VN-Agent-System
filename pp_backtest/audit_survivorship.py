from __future__ import annotations

"""
Audit survivorship / point-in-time (PIT) properties of the PP monthly universe.

This does NOT attempt to "fix" survivorship without data. It reports what we can
infer from existing artifacts:
- `pp_backtest/monthly_universe_eligibility.csv`
- the configured universe symbols file (default: config/universe_full_from_user.txt)
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd


_REPO = Path(__file__).resolve().parent.parent
_PP = Path(__file__).resolve().parent


@dataclass(frozen=True)
class SurvivorshipAudit:
    eligibility_csv: str
    universe_file: str
    symbols_in_universe_file: int
    symbols_in_eligibility_csv: int
    date_min: str
    date_max: str
    ever_inactive_symbols: int
    ever_inactive_examples: List[str]
    # Heuristic flags (cannot prove full survivorship control without authoritative listing/delist source)
    survivorship_risk: str
    notes: str


def _load_universe_symbols(path: Path) -> List[str]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [ln.strip().upper() for ln in lines if ln.strip() and not ln.strip().startswith("#")]


def run_audit(
    eligibility_path: Optional[Path] = None,
    universe_path: Optional[Path] = None,
) -> SurvivorshipAudit:
    elig_p = eligibility_path or (_PP / "monthly_universe_eligibility.csv")
    uni_p = universe_path or (_REPO / "config" / "universe_full_from_user.txt")

    df = pd.read_csv(elig_p)
    if "month_start" not in df.columns or "symbol" not in df.columns:
        raise ValueError("Eligibility CSV missing required columns: symbol, month_start")
    df["month_start"] = pd.to_datetime(df["month_start"])
    df["symbol"] = df["symbol"].astype(str).str.upper()
    if "active_flag" in df.columns:
        df["active_flag"] = df["active_flag"].astype(bool)
    else:
        df["active_flag"] = True

    uni_syms = _load_universe_symbols(uni_p)
    elig_syms = sorted(df["symbol"].unique().tolist())

    ever_inactive = df.groupby("symbol")["active_flag"].min() == False  # noqa: E712
    ever_inactive_syms = sorted(ever_inactive[ever_inactive].index.tolist())

    # Heuristic: if the universe input file is "from_user" and does not contain delisted names,
    # survivorship risk remains. We cannot confirm delisted completeness without external listing data.
    survivorship_risk = "Unknown"
    notes = (
        "This audit can only evaluate PIT mechanics inside the repo artifacts. "
        "Full survivorship elimination requires an authoritative listing/delist history or "
        "a historical constituents dataset. If `config/universe_full_from_user.txt` is a "
        "current-survivors list, survivorship bias remains."
    )
    if "from_user" in str(uni_p).lower():
        survivorship_risk = "Likely (universe source may be current-survivors list)"

    return SurvivorshipAudit(
        eligibility_csv=str(elig_p.relative_to(_REPO) if elig_p.is_relative_to(_REPO) else elig_p),
        universe_file=str(uni_p.relative_to(_REPO) if uni_p.is_relative_to(_REPO) else uni_p),
        symbols_in_universe_file=len(uni_syms),
        symbols_in_eligibility_csv=len(elig_syms),
        date_min=str(df["month_start"].min().date()),
        date_max=str(df["month_start"].max().date()),
        ever_inactive_symbols=len(ever_inactive_syms),
        ever_inactive_examples=ever_inactive_syms[:20],
        survivorship_risk=survivorship_risk,
        notes=notes,
    )


def main() -> None:
    audit = run_audit()
    out_dir = _REPO / "artifacts"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_json = out_dir / "survivorship_audit_pp.json"
    out_md = out_dir / "survivorship_audit_pp.md"

    out_json.write_text(json.dumps(asdict(audit), ensure_ascii=False, indent=2), encoding="utf-8")

    md = []
    md.append("# Survivorship / PIT Audit (PP)\n")
    md.append("## Facts\n")
    md.append(f"- **eligibility_csv**: `{audit.eligibility_csv}`\n")
    md.append(f"- **universe_file**: `{audit.universe_file}`\n")
    md.append(f"- **date_range**: {audit.date_min} → {audit.date_max}\n")
    md.append(f"- **symbols_in_universe_file**: {audit.symbols_in_universe_file}\n")
    md.append(f"- **symbols_in_eligibility_csv**: {audit.symbols_in_eligibility_csv}\n")
    md.append(f"- **symbols_ever_inactive (active_flag becomes False at some month_start)**: {audit.ever_inactive_symbols}\n")
    md.append(f"- **examples**: {', '.join(audit.ever_inactive_examples) if audit.ever_inactive_examples else 'None'}\n")
    md.append("\n## Interpretation\n")
    md.append(f"- **survivorship_risk**: {audit.survivorship_risk}\n")
    md.append(f"- **notes**: {audit.notes}\n")

    out_md.write_text("".join(md), encoding="utf-8")
    print(f"[audit_survivorship] wrote {out_json}")
    print(f"[audit_survivorship] wrote {out_md}")


if __name__ == "__main__":
    main()

