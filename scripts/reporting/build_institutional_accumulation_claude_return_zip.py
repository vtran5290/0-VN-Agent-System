"""
Package Claude Code review outputs for return to ChatGPT (Stage 4).

Usage:
  python -m scripts.reporting.build_institutional_accumulation_claude_return_zip --as-of 2026-04-30
"""
from __future__ import annotations

import argparse
import zipfile
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "outputs" / "review_packages"
ZIP_NAME = "institutional_accumulation_claude_return_chatgpt.zip"


def build(as_of: str) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    zpath = OUT / ZIP_NAME
    scans = REPO / "outputs" / "scans"
    candidates = [
        REPO / "RETURN_HANDOVER_TO_CHATGPT.md",
        REPO / "outputs" / "review_packages" / "RETURN_HANDOVER_TO_CHATGPT.md",
        scans / f"institutional_accumulation_claude_review_{as_of}.md",
        scans / f"institutional_accumulation_weekly_brief_{as_of}.md",
        scans / "METHODOLOGY_V11_COMPARISON_20260430.md",
        scans / "V11_VALIDATION_NOTE_20260430.md",
        scans / f"institutional_accumulation_{as_of}_top80.csv",
        scans / f"emerging_accumulation_{as_of}.csv",
    ]
    manifest: list[str] = []
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as zf:
        readme = f"""Claude Code return package — Institutional Accumulation Scan
Built: {datetime.now().isoformat(timespec="seconds")}
As-of: {as_of}

Paste RETURN_HANDOVER_TO_CHATGPT.md back into the ChatGPT Stage 1 thread.
"""
        zf.writestr("README.txt", readme)
        manifest.append("README.txt")
        for src in candidates:
            if not src.is_file():
                continue
            arc = src.name if src.parent == scans else f"handover/{src.name}"
            if "RETURN_HANDOVER" in src.name:
                arc = "RETURN_HANDOVER_TO_CHATGPT.md"
            zf.write(src, arc)
            manifest.append(arc)
        zf.writestr(
            "prompts/CURSOR_IMPLEMENTATION_TEMPLATE.md",
            (REPO / "docs/trading/CURSOR_IMPLEMENTATION_TEMPLATE.md").read_text(encoding="utf-8")
            if (REPO / "docs/trading/CURSOR_IMPLEMENTATION_TEMPLATE.md").is_file()
            else "",
        )
        manifest.append("prompts/CURSOR_IMPLEMENTATION_TEMPLATE.md")
        zf.writestr("MANIFEST.txt", "\n".join(sorted(manifest)))
    print(f"Wrote {zpath} ({zpath.stat().st_size / 1024:.1f} KB, {len(manifest)} files)")
    missing = [p for p in candidates if not p.is_file()]
    if missing:
        print("Note: missing (Claude not run yet):", ", ".join(p.name for p in missing))
    return zpath


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", default="2026-04-30")
    build(ap.parse_args().as_of)


if __name__ == "__main__":
    main()
