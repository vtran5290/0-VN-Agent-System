# Cloud Daily Report — Operator Guide

## How to Run

```bash
# EOD (after market close — full decision board)
python -m src.trading.cli cloud-daily-report --mode eod

# Pre-lunch preview (before 11:30 session break)
python -m src.trading.cli cloud-daily-report --mode pre-lunch

# Pre-ATC preview (before 14:30 ATC session)
python -m src.trading.cli cloud-daily-report --mode pre-atc

# Auto-detect mode (uses intraday if CSV < 6h old, else EOD)
python -m src.trading.cli cloud-daily-report --mode auto

# Override scan path
python -m src.trading.cli cloud-daily-report --mode eod --scan-path path/to/scan.csv
```

Output files are written to `data/research/reports/`:
- `cloud_daily_report_latest.html` — primary HTML report
- `cloud_daily_report_latest.md` — markdown summary
- `cloud_daily_report_latest.json` — machine-readable payload
- `cloud_daily_report_YYYYMMDD_HHMM.html/md` — timestamped copies

---

## What Each Mode Means

| Mode | When to use | Source of truth |
|---|---|---|
| `eod` | After market close (15:15+) | `phase36_daily_scan_latest.csv` |
| `pre-lunch` | 09:00–11:29 morning session | `phase36_intraday_scan_latest.csv` + EOD delta |
| `pre-atc` | 13:00–14:29 afternoon session | `phase36_intraday_scan_latest.csv` + EOD delta |
| `auto` | Anytime — system detects | Intraday if fresh (< 6h), else EOD |

Daily scan is source of truth. Intraday is preview only.

---

## How to Read the Action Board

The report is divided into sections A–I.

**Section A — Header badges:** Mode, VNINDEX regime, breadth zone, T1/T2 permission.

**Section B — Decision cards:**
- **ACTION NOW**: What needs operator attention immediately (new T1s, exits, signal today).
- **WATCH/PREPARE**: Monitors, S3 paper setups, T2 candidates.
- **DO NOT DO**: Hard rules — no T2 in defense breadth, no S3 live capital, no AFL orders.

**Section C — A3 Action Board:**
- Group 1: New T1 candidates — sorted by `final_action` (NEW_T1 first), then `a3_rank_score` descending.
- Group 2: T2/pullback candidates.
- Group 3: Exit-review rows (trail breach, TP1 partial).
- Group 4: Hold-only rows (top 10 displayed; rest in appendix).

**Section D — Portfolio Overlay:** Each holding checked against current scan. Flags trail breach and near-TP1 rows.

**Section E — Intraday Preview Board** (only in pre-lunch / pre-atc mode): Shows `would_be_final_action` for planning only. All rows show `auto_order_allowed=False`.

**Section F — S3 Radar:** Paper-shadow candidates with dashed border. Never real capital.

**Section G — Market context:** VNINDEX regime, breadth %, zone, permissions, sector stress, liquidity warnings.

**Section H — Delta:** What changed since the previous report (new candidates added/removed, breadth zone change, regime change).

**Section I — Appendix:** Full collapsible scan table, files used.

---

## A3 vs S3

A3 is the production engine.

S3 is radar / paper-shadow.

- A3 generates `final_action` that drives OMS and order intents.
- S3 runs as a paper-shadow tracking exercise alongside A3. It never generates live orders.
- `s3_no_real_order_flag=True` on every S3 row is a safety invariant — any False triggers a NEEDS_REVIEW warning.
- S3 section in the report is visually distinct (dashed border, dark background) to prevent confusion.

---

## EOD vs Intraday

**EOD scan** (`final_action`):
- Computed after market close using full-day OHLCV.
- Drives actual order intents and paper-account workflows.
- `a3_signal_today=True` means the cloud signal triggered today; entry fill is planned for the next session open.

**Intraday scan** (`final_action=INTRADAY_PREVIEW`, `would_be_final_action`):
- Computed during session using partial-day quotes.
- `would_be_final_action` is what A3 *would* decide if market closed right now.
- Never drives order routing. Never routes to OMS. `auto_order_allowed=False` always.
- Used for planning and operator awareness only.

Intraday is preview only.

---

## Pending-Entry Levels Explanation

When `a3_signal_today=True`:
- The A3 cloud signal was confirmed on today's bar.
- `pb_trigger_price`, `tp1_price`, `trail_price` may show as **pending*** in the action board.
- This means levels will be computed from the confirmed entry bar (next-open fill).

a3_signal_today means signal confirmed today; planned fill is next session open.

Do not place orders at AFL price levels — AFL is visual cockpit. Use the computed prices from the scan.

---

## Breadth Rule Explanation

The A3 breadth system uses `pct_cloud_bull_a3` (percentage of A3 universe in cloud-bull state):

| Breadth zone | `pct_cloud_bull_a3` | T1 effect | T2 effect |
|---|---|---|---|
| `normal` | ≥ 50% | Allowed | Allowed |
| `caution` | 40–49% | Allowed (may need manual review) | Allowed with caution |
| `defense` | < 40% | May require manual review | BLOCKED |

Breadth <40% blocks T2 only. VNINDEX bear blocks new T1. Sector L4 = dashboard warning only.

`breadth_t2_permission=False` in the scan means T2 is blocked by the system. The report will show `NO_T2_BREADTH` rows in Group 2 and a "Do not add T2" in the DO NOT DO card.

---

## What to Do at Each Time

### Pre-lunch (09:00–11:29)
1. Run: `python -m src.trading.cli cloud-daily-report --mode pre-lunch`
2. Read Section E (intraday preview) to see `would_be` actions.
3. Do NOT place orders based on intraday preview.
4. Note any NEW_T1 candidates in `would_be_final_action` — these need EOD confirmation.

### Pre-ATC (13:00–14:29)
1. Run: `python -m src.trading.cli cloud-daily-report --mode pre-atc`
2. Check intraday VNINDEX overlay vs EOD regime.
3. Check exit candidates — if trail is breached intraday, prepare for EOD confirmation.
4. Do NOT route any orders from intraday preview.

### EOD (15:15+)
1. Run: `python -m src.trading.cli cloud-daily-report --mode eod`
2. Read Section B ACTION NOW — these are the real decisions.
3. For NEW_T1 rows: review `a3_rank_score` order, check pending* levels if `a3_signal_today=True`.
4. For exit rows in holdings: confirm trail breach or TP1 partial action.
5. For T2 rows: only proceed if `breadth_t2_permission=True`.
6. Run `python -m src.trading.cli build-intents` to generate order intents from EOD scan.

---

## What NOT to Do

- Do not place live orders based on intraday `would_be_final_action`.
- Do not trade S3 paper-shadow rows as live capital.
- Do not use AFL chart visuals as the order price source.
- Do not duplicate positions already in holdings (check Section D).
- Do not add T2 when breadth zone is `defense` (breadth < 40%).
- Do not ignore `NEEDS_REVIEW` status — investigate warnings before proceeding.

---

## Rank Score

a3_rank_score affects review order only.

It determines which NEW_T1 candidates appear at the top of the action board. It does not override `final_action` logic or position sizing rules. A higher `a3_rank_score` means review that candidate first, not that it should receive a larger allocation.

---

## Key Invariants

These are enforced by the report's safety checker. Any violation sets `report_status=NEEDS_REVIEW`:

| Invariant | Expected value |
|---|---|
| `auto_order_allowed` in intraday rows | Always `False` |
| `final_action` in intraday rows | Always `INTRADAY_PREVIEW` |
| `s3_no_real_order_flag` | Always `True` |
| Scan file available | At least one fallback CSV found |
