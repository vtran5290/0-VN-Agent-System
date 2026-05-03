# Paste one line into this chat (then agent runs terminal)

From **repo root**. Prefer **PowerShell 7** if installed:

AM_OPEN: `@daily run: pwsh -NoProfile -File scripts/research/daily_slots.ps1 AM_OPEN`
AM_MID: `@daily run: pwsh -NoProfile -File scripts/research/daily_slots.ps1 AM_MID`
PM_CLOSE: `@daily run: pwsh -NoProfile -File scripts/research/daily_slots.ps1 PM_CLOSE`

**Windows — no `pwsh` on PATH:** use Windows PowerShell 5.1 (same script):

`powershell -NoProfile -File scripts/research/daily_slots.ps1 PM_CLOSE`

**Any OS — skip the wrapper:** same behavior as the `.ps1` (it only `cd`s to repo root and calls node):

`node scripts/research/daily_donchian_ema_slot_scan.mjs --slot=PM_CLOSE` (swap `AM_OPEN` / `AM_MID` / `PM_CLOSE`)

Output keys: `BUY|L1|L2|L3` `RB` RawBuy `G` new DC_Buy pulse `NK` RawBuy but no pulse (63-bar lock) `SELL|E` CH or MAE exit bar.
