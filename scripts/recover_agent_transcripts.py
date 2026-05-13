"""
Recover readable chat markdown files from local Cursor agent-transcripts JSONL logs.
"""
from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path.home() / ".cursor" / "projects"
OUT_DIR = Path("cursor_chat_export") / "recovered_from_agent_transcripts"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def clean_name(name: str, max_len: int = 90) -> str:
    name = re.sub(r'[\\/:*?"<>|]+', "_", name).strip().strip(".")
    return (name or "untitled")[:max_len]


def extract_text(content: object) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, str):
                chunks.append(item)
            elif isinstance(item, dict):
                t = item.get("text")
                if isinstance(t, str) and t.strip():
                    chunks.append(t.strip())
        return "\n".join(chunks).strip()
    if isinstance(content, dict):
        for key in ("text", "content", "message"):
            value = content.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def best_title(first_user_text: str, fallback: str) -> str:
    if not first_user_text:
        return fallback
    title = first_user_text.strip().splitlines()[0]
    title = title.replace("<user_query>", "").replace("</user_query>", "").strip()
    return title or fallback


def render_markdown(records: list[dict], transcript_id: str) -> tuple[str, str]:
    messages: list[tuple[str, str]] = []
    first_user = ""

    for rec in records:
        role = str(rec.get("role", "")).strip().lower()
        msg = rec.get("message", {})
        content = msg.get("content", []) if isinstance(msg, dict) else []
        text = extract_text(content)
        if not text:
            continue
        if role == "assistant" and "[REDACTED]" in text:
            text = text.replace("[REDACTED]", "").strip()
            if not text:
                continue
        if role == "user" and not first_user:
            first_user = text
        label = "User" if role == "user" else ("Assistant" if role == "assistant" else role.title() or "Message")
        messages.append((label, text))

    title = best_title(first_user, transcript_id[:8])
    lines = [f"# {title}", "", f"> transcript_id: `{transcript_id}`", "", "---", ""]
    for label, text in messages:
        lines.extend((f"### {label}", "", text, "", "---", ""))
    return title, "\n".join(lines).strip() + "\n"


def main() -> None:
    transcript_files = sorted(
        p for p in ROOT.glob("**/agent-transcripts/**/*.jsonl") if "\\subagents\\" not in str(p)
    )
    exported = 0
    skipped = 0

    for path in transcript_files:
        try:
            raw_lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            skipped += 1
            continue
        rows: list[dict] = []
        for line in raw_lines:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if isinstance(obj, dict):
                rows.append(obj)
        if not rows:
            skipped += 1
            continue

        transcript_id = path.stem
        title, md = render_markdown(rows, transcript_id)
        if "### " not in md:
            skipped += 1
            continue

        out_name = f"{clean_name(title)}__{transcript_id}.md"
        out_path = OUT_DIR / out_name
        out_path.write_text(md, encoding="utf-8")
        exported += 1

    print(f"Recovered: {exported}")
    print(f"Skipped: {skipped}")
    print(f"Output: {OUT_DIR.resolve()}")


if __name__ == "__main__":
    main()

