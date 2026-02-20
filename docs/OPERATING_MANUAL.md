# Operating Manual — VN Agent System

## Non-negotiables

- **Facts-first.** Separate FACTS vs INTERPRETATION.
- **No hallucination:** If data is missing, say "Unknown" and list what would confirm/deny.
- **Always end weekly report with:**
  1. Signals to monitor next week
  2. If X happens → do Y

## Framework tags

- **Buffett/Munger:** moat, ROIC, capital allocation, debt discipline
- **Minervini/O'Neil/Morales:** trend, base, volume, risk control

## Output style

- Bullet-heavy, quantified when possible.
- Use Vietnam context and transmission channels: rates, credit, fiscal, FX, sentiment.

## Output Format Rules

Weekly report **MUST** include (in this order):

- **Global Macro + Fed:** what changed, what matters, what to watch next
- **Vietnam Policy:** new laws/resolutions/circulars + transmission map
- **Sectors & Companies:** earnings/broker notes + catalysts/risks
- **Decision layer:** Top 3 actions, Top 3 risks, Watchlist updates
- **End with:**
  - Signals to monitor next week
  - If X happens → do Y

## Core inputs (MVP — 8 số tối thiểu)

Pareto 20% data → 80% quyết định. Điền trong `data/raw/manual_inputs.json`:
- **Global (3):** ust_2y, ust_10y, dxy
- **Vietnam (3):** omo_net, interbank_on, credit_growth_yoy
- **Market (2):** vnindex_level, distribution_days_rolling_20

Chi tiết: `docs/runbook.md`.

## Watchlist (editable)

Edit `config/watchlist.txt` to change symbols. Current default:

SSI, VCI, SHS, TCX, MBB, STB, SHB, DCM, PVD, PC1, DXG, VSC, GMD, MWG
