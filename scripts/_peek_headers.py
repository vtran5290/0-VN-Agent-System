import sqlite3, json, os

APPDATA = os.environ['APPDATA']
db = rf"{APPDATA}\Cursor\User\globalStorage\state.vscdb"
con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
cur = con.cursor()
cur.execute("SELECT value FROM [ItemTable] WHERE key='composer.composerHeaders'")
raw = cur.fetchone()[0]
if isinstance(raw, (bytes, bytearray)):
    raw = raw.decode('utf-8', errors='replace')
data = json.loads(raw)
print(type(data))
if isinstance(data, dict):
    keys = list(data.keys())[:3]
    print("dict keys sample:", keys)
    for k in keys:
        print(f"  {k}: {type(data[k])} -> {str(data[k])[:200]}")
elif isinstance(data, list):
    print(f"list len={len(data)}, first item type={type(data[0])}")
    print("First item:", str(data[0])[:500])
    if len(data) > 1:
        print("Second item:", str(data[1])[:200])
con.close()
