# Paste one line into this chat (then agent runs terminal)

AM_OPEN: `@daily run: pwsh -NoProfile -File scripts/research/daily_slots.ps1 AM_OPEN`
AM_MID: `@daily run: pwsh -NoProfile -File scripts/research/daily_slots.ps1 AM_MID`
PM_CLOSE: `@daily run: pwsh -NoProfile -File scripts/research/daily_slots.ps1 PM_CLOSE`

Direct node: `node scripts/research/daily_donchian_ema_slot_scan.mjs --slot=AM_OPEN`

Output keys: `BUY|L1|L2|L3` `RB` RawBuy `G` new DC_Buy pulse `NK` RawBuy but no pulse (63-bar lock) `SELL|E` CH or MAE exit bar.
