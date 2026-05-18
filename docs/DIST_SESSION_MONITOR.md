# VNINDEX distribution — per-session monitor

Use this workflow in **this chat** (or any Cursor session) after each HOSE close.

## Run (after market close)

```powershell
cd "c:\Users\LOLII\Documents\V\0. VN Agent System"
.\monitor_vnindex_dist_session.cmd
```

Or with a note:

```powershell
.\.venv\Scripts\python.exe scripts\monitor_vnindex_distribution_session.py --fetch --refresh-ex-vin --note "post-close"
```

Requires `FIREANT_TOKEN` in `.env` when using `--fetch`.

## Outputs (SSOT for the chat)

| File | Purpose |
|------|---------|
| `data/alerts/dist_session_latest.json` | Machine-readable latest snapshot |
| `data/decision/dist_session_alert.md` | Human-readable alert (FACTS / INTERPRETATION) |
| `data/alerts/dist_session_log.jsonl` | Append-only history (one line per run) |

## Alert levels

| Level | Typical trigger |
|-------|-----------------|
| **GREEN** | dist_20 ≤ 2, dist_10 ≤ 1, no cluster |
| **YELLOW** | dist_20 = 3 or dist_10 ≥ 2 or **today = distribution day** |
| **ORANGE** | dist_20 ≥ 4 or dist_10 ≥ 4 or 3+ dist in last 5 sessions |
| **RED** | dist_20 ≥ 5 or (dist_20 ≥ 4 and below MA50) |

**Composite** = max(full, ex-VIN).

## In chat

After you run the script, message e.g.:

- `check dist` / `monitor phân phối` → agent reads `dist_session_latest.json` + latest log line
- `so sánh với 3-4/2024` → agent uses reference table in the JSON + log

Distribution rule: close ≤ prior × (1 − 0.2%) and volume > prior volume (O'Neil/Morales).

ex-VIN: proxy series VIC+VHM+VRE (VPL excluded per VIN baseline). Prefer VIN basket lines in JSON for “big hand” read.
