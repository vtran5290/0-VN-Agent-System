from __future__ import annotations
from pathlib import Path
import shutil

FILES = [
    ("data/raw/manual_inputs.json", "data/raw/manual_inputs_prev.json"),
    ("data/raw/weekly_notes.json", "data/raw/weekly_notes_prev.json"),
    ("data/raw/watchlist_scores.json", "data/raw/watchlist_scores_prev.json"),
    ("data/raw/tech_status.json", "data/raw/tech_status_prev.json"),
]

def roll() -> None:
    for src, dst in FILES:
        s = Path(src)
        d = Path(dst)
        if s.exists():
            d.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(s, d)
            print(f"Rolled: {src} -> {dst}")
        else:
            print(f"Skip (missing): {src}")

if __name__ == "__main__":
    roll()
