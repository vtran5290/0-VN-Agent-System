"""Render institutional_accumulation_weekly_brief_{date}.html from markdown."""
from __future__ import annotations

import html
import re
from typing import List

_CSS = """
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap');
:root {
  --bg:#0d0f12; --panel:#13161b; --card:#181c22; --border:#252a35;
  --accent:#00c896; --amber:#f0a030; --text:#d8dde8; --dim:#7a8399; --muted:#4a5168;
}
body{background:var(--bg);color:var(--text);font-family:"IBM Plex Sans",sans-serif;font-size:14px;line-height:1.65;margin:0;padding:24px}
.wrap{max-width:920px;margin:0 auto}
.doc{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:22px 26px}
h1{font-size:1.35rem;font-weight:700;margin:0 0 12px}
h2{font-size:1.05rem;font-weight:700;color:var(--accent);margin:22px 0 10px;padding-bottom:6px;border-bottom:1px solid var(--border)}
h3{font-size:.95rem;font-weight:600;margin:16px 0 8px}
p{margin:8px 0}
ul,ol{margin:8px 0 8px 20px}
li{margin:4px 0}
blockquote{margin:12px 0;padding:10px 14px;border-left:3px solid var(--amber);background:rgba(240,160,48,.08);color:var(--dim)}
table{width:100%;border-collapse:collapse;font-size:12px;margin:10px 0}
th,td{border:1px solid var(--border);padding:6px 10px;text-align:left;vertical-align:top}
th{background:var(--panel);color:var(--muted);font-size:10px;text-transform:uppercase}
tr:nth-child(even) td{background:rgba(255,255,255,.02)}
hr{border:none;border-top:1px solid var(--border);margin:18px 0}
code,.mono{font-family:"IBM Plex Mono",monospace;font-size:12px;color:var(--accent)}
.meta{font-size:12px;color:var(--dim);margin-bottom:14px}
.footer{font-size:11px;color:var(--muted);margin-top:18px}
strong{color:#eef2f8}
"""


def _inline(s: str) -> str:
    esc = html.escape(s)
    esc = re.sub(r"`([^`]+)`", r'<code>\1</code>', esc)
    esc = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", esc)
    return esc


def markdown_to_html_body(md: str) -> str:
    """Minimal markdown → HTML (headings, lists, tables, blockquotes)."""
    lines = md.replace("\r\n", "\n").split("\n")
    out: List[str] = []
    i = 0
    in_ul = False
    in_ol = False

    def close_lists() -> None:
        nonlocal in_ul, in_ol
        if in_ul:
            out.append("</ul>")
            in_ul = False
        if in_ol:
            out.append("</ol>")
            in_ol = False

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("|") and "|" in stripped[1:]:
            close_lists()
            table_rows: List[str] = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_rows.append(lines[i].strip())
                i += 1
            if len(table_rows) >= 2:
                sep = table_rows[1]
                if re.match(r"^\|[\s\-:|]+\|$", sep):
                    header = [c.strip() for c in table_rows[0].strip("|").split("|")]
                    out.append("<table><thead><tr>")
                    for h in header:
                        out.append(f"<th>{_inline(h)}</th>")
                    out.append("</tr></thead><tbody>")
                    for row in table_rows[2:]:
                        cells = [c.strip() for c in row.strip("|").split("|")]
                        out.append("<tr>")
                        for c in cells:
                            out.append(f"<td>{_inline(c)}</td>")
                        out.append("</tr>")
                    out.append("</tbody></table>")
            continue

        if stripped == "---":
            close_lists()
            out.append("<hr/>")
            i += 1
            continue

        if stripped.startswith("### "):
            close_lists()
            out.append(f"<h3>{_inline(stripped[4:])}</h3>")
            i += 1
            continue
        if stripped.startswith("## "):
            close_lists()
            out.append(f"<h2>{_inline(stripped[3:])}</h2>")
            i += 1
            continue
        if stripped.startswith("# "):
            close_lists()
            out.append(f"<h1>{_inline(stripped[2:])}</h1>")
            i += 1
            continue

        if stripped.startswith("> "):
            close_lists()
            out.append(f"<blockquote>{_inline(stripped[2:])}</blockquote>")
            i += 1
            continue

        if stripped.startswith("- "):
            if not in_ul:
                close_lists()
                out.append("<ul>")
                in_ul = True
            out.append(f"<li>{_inline(stripped[2:])}</li>")
            i += 1
            continue

        m = re.match(r"^(\d+)\.\s+(.*)$", stripped)
        if m:
            if not in_ol:
                close_lists()
                out.append("<ol>")
                in_ol = True
            out.append(f"<li>{_inline(m.group(2))}</li>")
            i += 1
            continue

        if not stripped:
            close_lists()
            i += 1
            continue

        close_lists()
        out.append(f"<p>{_inline(stripped)}</p>")
        i += 1

    close_lists()
    return "\n".join(out)


def render_weekly_brief_html(md: str, *, scan_date: str) -> str:
    body = markdown_to_html_body(md)
    title = f"Institutional Accumulation Weekly Brief — {html.escape(scan_date)}"
    return (
        f"<!DOCTYPE html><html lang='en'><head><meta charset='UTF-8'>"
        f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{title}</title><style>{_CSS}</style></head><body>"
        f"<div class='wrap'><div class='doc'>{body}</div>"
        f"<p class='footer'>Research only · does not set final_action · "
        f"generated {html.escape(scan_date)}</p></div></body></html>"
    )
