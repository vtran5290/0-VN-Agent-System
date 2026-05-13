import sqlite3
import json
import os
import sys

APPDATA = os.environ['APPDATA']

dbs = [
    rf"{APPDATA}\Cursor\User\globalStorage\state.vscdb",
    rf"{APPDATA}\Cursor\Cursor\User\globalStorage\state.vscdb",
]

CHAT_KEYWORDS = ['chat', 'composer', 'cursor', 'conversation', 'history',
                 'bubble', 'aichat', 'aiconversation', 'tabs']

def scan_db(path):
    if not os.path.exists(path):
        print(f"SKIP (not found): {path}")
        return
    print(f"\n=== {path} ===")
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    cur = con.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    print(f"Tables: {tables}")
    for table in tables:
        try:
            cur.execute(f"SELECT key, length(value) FROM [{table}] ORDER BY key")
            rows = cur.fetchall()
            print(f"\n  [{table}] — {len(rows)} keys")
            for key, sz in rows:
                kl = str(key).lower()
                if any(x in kl for x in CHAT_KEYWORDS):
                    print(f"    *** {key}  [{sz} bytes]")
        except Exception as e:
            print(f"  [{table}] error: {e}")
    con.close()

for db in dbs:
    scan_db(db)
