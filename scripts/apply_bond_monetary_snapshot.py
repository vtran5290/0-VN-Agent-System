"""Apply bond_monetary_snapshot pack: merge into data/state/bond_monetary_snapshot.json (non-destructive)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_PACK = REPO / "data" / "raw" / "bond_monetary_snapshot.json"
STATE_DIR = REPO / "data" / "state"
OUT_PATH = STATE_DIR / "bond_monetary_snapshot.json"


def _deep_merge_non_destructive(target: dict, source: dict) -> None:
    """Merge source into target; only set keys present in source. None in source does not delete target key."""
    for key, value in source.items():
        if value is None:
            continue
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _deep_merge_non_destructive(target[key], value)
        else:
            target[key] = value


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply bond/monetary snapshot into state (non-destructive merge).")
    parser.add_argument("--pack", default=str(DEFAULT_PACK), help="Path to bond_monetary_snapshot JSON.")
    args = parser.parse_args()
    pack_path = Path(args.pack)
    if not pack_path.exists():
        print(f"Missing pack: {pack_path}")
        return
    data = json.loads(pack_path.read_text(encoding="utf-8"))
    snapshot = data.get("bond_monetary_snapshot")
    if not isinstance(snapshot, dict):
        print("Pack has no bond_monetary_snapshot object.")
        return
    existing: dict = {}
    if OUT_PATH.exists():
        try:
            existing = json.loads(OUT_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    _deep_merge_non_destructive(existing, snapshot)
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Applied bond_monetary_snapshot -> {OUT_PATH}")


if __name__ == "__main__":
    main()
