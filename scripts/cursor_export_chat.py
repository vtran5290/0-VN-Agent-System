"""
Export all Cursor chat history to markdown files.
Merges data from both state.vscdb instances.
Output: cursor_chat_export/<date>_<title>.md
"""
import sqlite3
import json
import os
import re
from pathlib import Path
from datetime import datetime

APPDATA = os.environ['APPDATA']
DB_PATHS = [
    rf"{APPDATA}\Cursor\User\globalStorage\state.vscdb",
    rf"{APPDATA}\Cursor\Cursor\User\globalStorage\state.vscdb",
]
OUT_DIR = Path("cursor_chat_export")
OUT_DIR.mkdir(exist_ok=True)


def open_ro(path):
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def ts(ms):
    if not ms:
        return ''
    try:
        return datetime.fromtimestamp(int(ms) / 1000).strftime('%Y-%m-%d %H:%M')
    except Exception:
        return str(ms)


def safe_fn(s, maxlen=70):
    s = re.sub(r'[\\/:*?"<>|]', '_', str(s)).strip().strip('.')
    return (s or 'untitled')[:maxlen]


def decode(v):
    if isinstance(v, (bytes, bytearray)):
        return v.decode('utf-8', errors='replace')
    return v


def parse_json(v):
    try:
        return json.loads(decode(v))
    except Exception:
        return None


def extract_text(v):
    if v is None:
        return '', ''
    d = parse_json(v)
    if not d:
        raw = decode(v)
        return '', (raw[:300] if raw else '')
    role = str(d.get('type') or d.get('role') or '')
    parts = []
    for f in ('text', 'content', 'message', 'rawText', 'displayText'):
        val = d.get(f)
        if isinstance(val, str) and val.strip():
            parts.append(val)
            break
        if isinstance(val, list):
            for item in val:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    t = item.get('text') or item.get('content') or ''
                    if t:
                        parts.append(str(t))
    # richText fallback
    if not parts:
        rich = d.get('richText') or d.get('blocks')
        if rich:
            try:
                if isinstance(rich, str):
                    rich = json.loads(rich)
                for block in (rich if isinstance(rich, list) else [rich]):
                    for el in (block.get('children') or []):
                        t = el.get('text', '')
                        if t:
                            parts.append(t)
            except Exception:
                pass
    return role, '\n'.join(p for p in parts if p).strip()


# ── Pass 1: collect all composers ──────────────────────────────────────────
all_composers = {}   # composerId -> meta dict
all_bubbles   = {}   # composerId -> {msgId: value}
all_comp_data = {}   # composerId -> composerData dict

for dbp in DB_PATHS:
    if not os.path.exists(dbp):
        continue
    print(f"Reading: {dbp}")
    con = open_ro(dbp)
    cur = con.cursor()

    tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]

    # composer headers
    if 'ItemTable' in tables:
        cur.execute("SELECT value FROM [ItemTable] WHERE key='composer.composerHeaders'")
        row = cur.fetchone()
        if row:
            h = parse_json(row[0]) or {}
            raw_list = h.get('allComposers') or h.get('composers') or []
            if isinstance(raw_list, list):
                for c in raw_list:
                    if isinstance(c, dict):
                        cid = c.get('composerId') or c.get('id')
                        if cid:
                            all_composers.setdefault(cid, c)
            elif isinstance(h, dict):
                for cid, c in h.items():
                    if isinstance(c, dict):
                        all_composers.setdefault(cid, c)
            print(f"  composers so far: {len(all_composers)}")

    # bubbles + composerData from cursorDiskKV
    if 'cursorDiskKV' in tables:
        cur.execute("SELECT key, value FROM [cursorDiskKV]")
        for key, value in cur.fetchall():
            key = decode(key)
            if key.startswith('bubbleId:'):
                parts = key.split(':', 2)
                if len(parts) == 3:
                    _, cid, mid = parts
                    all_bubbles.setdefault(cid, {})[mid] = value
            elif key.startswith('composerData:'):
                cid = key[len('composerData:'):]
                d = parse_json(value)
                if d:
                    all_comp_data[cid] = d
        print(f"  composers with bubbles so far: {len(all_bubbles)}")

    con.close()

print(f"\nTotal composers: {len(all_composers)}")
print(f"Composers with bubbles: {len(all_bubbles)}")

# ── Pass 2: export ──────────────────────────────────────────────────────────
exported = 0
skipped_empty = 0

for cid, meta in all_composers.items():
    bubbles = all_bubbles.get(cid, {})
    if not bubbles:
        skipped_empty += 1
        continue

    comp_data = all_comp_data.get(cid, {})
    title = (comp_data.get('name') or comp_data.get('title') or
             meta.get('name') or meta.get('title') or cid[:8])
    created = ts(meta.get('createdAt') or comp_data.get('createdAt'))
    updated = ts(meta.get('lastUpdatedAt') or meta.get('updatedAt') or comp_data.get('updatedAt'))

    # determine message order
    ordered_ids = comp_data.get('bubbleIds') or comp_data.get('messageIds') or []
    if ordered_ids:
        ordered = [(oid, bubbles[oid]) for oid in ordered_ids if oid in bubbles]
        seen_ids = set(ordered_ids)
        for mid, val in bubbles.items():
            if mid not in seen_ids:
                ordered.append((mid, val))
    else:
        ordered = list(bubbles.items())

    # build markdown
    date_prefix = created[:10] if created else 'nodate'
    fname = safe_fn(f"{date_prefix}_{title}")
    outpath = OUT_DIR / f"{fname}.md"
    i = 1
    while outpath.exists():
        outpath = OUT_DIR / f"{fname}_{i}.md"
        i += 1

    ROLE_LABEL = {
        'user': '**User**', 'human': '**User**',
        'assistant': '**Assistant**', 'ai': '**Assistant**',
        '1': '**User**', '2': '**Assistant**',
    }

    lines = [
        f"# {title}", "",
        f"> id: `{cid}`  ",
        f"> created: {created}  |  updated: {updated}  |  messages: {len(ordered)}",
        "", "---", "",
    ]

    msg_count = 0
    for mid, val in ordered:
        role, text = extract_text(val)
        if not text:
            continue
        label = ROLE_LABEL.get(role.lower(), f'**{role or "msg"}**')
        lines += [f"### {label}", "", text, "", "---", ""]
        msg_count += 1

    if msg_count == 0:
        skipped_empty += 1
        continue

    outpath.write_text('\n'.join(lines), encoding='utf-8')
    exported += 1

print(f"\nDone.")
print(f"  Exported:     {exported} conversations")
print(f"  Skipped (empty): {skipped_empty}")
print(f"  Output: {OUT_DIR.resolve()}")

# list files
files = sorted(OUT_DIR.glob('*.md'), key=lambda f: f.stat().st_size, reverse=True)
print(f"\nFiles ({len(files)} total):")
for f in files[:20]:
    kb = f.stat().st_size / 1024
    print(f"  {f.name}  ({kb:.0f} KB)")
if len(files) > 20:
    print(f"  ... and {len(files)-20} more")
