# filter_universe.py
# Với mỗi symbol trong list 186:
# 1. Load OHLCV từ 2018
# 2. Check: có đủ 252*4 bars (4 năm) không?
# 3. Tính ADTV = mean(close * volume) trên 2020-2022
# 4. Giữ nếu ADTV > 5e9 VND và n_bars >= 1000
# Output: filtered_universe.txt

from __future__ import annotations
import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.intake.fireant_historical import fetch_historical

# Cấu hình
START = "2018-01-01"
END_2022 = "2022-12-31"
ADTV_START = "2020-01-01"
ADTV_END = "2022-12-31"
MIN_BARS = 1000  # 252*4 ≈ 1008; dùng 1000 theo spec
MIN_ADTV_VND = 5e9  # 5 tỷ VND
DEFAULT_INPUT = REPO / "config" / "universe_186.txt"
DEFAULT_OUTPUT = REPO / "filtered_universe.txt"


def load_symbols(path: Path) -> list[str]:
    """Một symbol mỗi dòng, bỏ trống và comment #."""
    if not path.exists():
        raise FileNotFoundError(f"Symbol list not found: {path}")
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    out = []
    for ln in lines:
        ln = ln.split("#")[0].strip()
        if ln:
            out.append(ln)
    return out


def compute_adtv_2020_2022(rows: list) -> float:
    """ADTV = mean(close * volume) trên 2020-2022 (VND). Pure Python, no pandas."""
    turnovers: list[float] = []
    for r in rows:
        d = (r.d or "")[:10]
        if ADTV_START <= d <= ADTV_END:
            vol = r.v if r.v is not None else 0.0
            turnovers.append(r.c * vol)
    if not turnovers:
        return 0.0
    return sum(turnovers) / len(turnovers)


def main() -> None:
    parser = argparse.ArgumentParser(description="Filter universe by bars and ADTV 2020-2022")
    parser.add_argument(
        "--input", "-i",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"Input: one symbol per line (default: {DEFAULT_INPUT})",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output file (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Log mỗi symbol")
    args = parser.parse_args()

    symbols = load_symbols(args.input)
    print(f"Loaded {len(symbols)} symbols from {args.input}")

    passed: list[str] = []
    for i, sym in enumerate(symbols, 1):
        try:
            rows = fetch_historical(sym, START, END_2022)
        except Exception as e:
            if args.verbose:
                print(f"  [{i}/{len(symbols)}] {sym}: error {e}")
            continue

        n_bars = len(rows)
        if n_bars < MIN_BARS:
            if args.verbose:
                print(f"  [{i}/{len(symbols)}] {sym}: n_bars={n_bars} < {MIN_BARS}")
            continue

        adtv = compute_adtv_2020_2022(rows)
        if adtv < MIN_ADTV_VND:
            if args.verbose:
                print(f"  [{i}/{len(symbols)}] {sym}: ADTV={adtv/1e9:.2f}B < 5B")
            continue

        passed.append(sym)
        if args.verbose:
            print(f"  [{i}/{len(symbols)}] {sym}: n_bars={n_bars}, ADTV={adtv/1e9:.2f}B VND OK")

    args.output.write_text("\n".join(passed) + ("\n" if passed else ""), encoding="utf-8")
    print(f"Passed: {len(passed)} symbols -> {args.output}")


if __name__ == "__main__":
    main()
