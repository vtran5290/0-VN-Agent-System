# S3 Shadow Gate Tests

Date: 2026-05-16 (updated Round 2) | Classification: PAPER_TRADE_SHADOW

20 behavioral tests covering all S3 hard invariants.
Status: SPEC ONLY — code not yet implemented. Tests define required behavior.

---

## A — max_hold and Exit Enforcement

### Test 1 — max_hold=60 Hard Enforcement

**What to check:** A paper S3 position entered at bar 0 must force-exit at bar 60, regardless of P&L.

**Pass condition:** `s3_shadow_max_hold_remaining` reaches 0 on bar 60 and `s3_shadow_final_action = S3_SHADOW_EXIT` with `exit_reason = MAX_HOLD_60`.

**Fail condition:** Position held past bar 60 for any reason (profit, "let it run", config change, etc.).

**Code path:** `s3_shadow_bars_since >= 60` → force exit log.

---

### Test 2 — S3 Shadow Trail Uses 3.5×ATR14 (Not A3's 2.5×)

**What to check:** `s3_shadow_trail_price = peak_close - 3.5 * ATR14`.

**Pass condition:** `s3_shadow_trail_price` differs from A3 `trail_price` on the same symbol.

**Fail condition:** `s3_shadow_trail_price = peak_close - 2.5 * ATR14` (A3 multiplier applied to S3 — wrong).

---

### Test 3 — S3 Shadow AFL max_hold Parameter Locked

**What to check:** In `Cloud_Strategy_S3_21_55_PAPER_SHADOW_MAX60.afl`, Param range is [60, 60].

**Pass condition:** `Param("Max Hold...", 60, 60, 60, 1)` — min=max=default=60.

**Fail condition:** Any range that allows values other than 60 (e.g., `Param(..., 60, 1, 500, 1)`).

---

### Test 4 — S3 Shadow Exit on Trail Stop

**What to check:** If close falls below `peak − 3.5×ATR14` at bars 6–59, paper exit fires.

**Pass condition:** `s3_shadow_final_action = S3_SHADOW_EXIT` and `exit_reason = TRAIL_3.5ATR`.

**Fail condition:** Trail exit doesn't fire, or fires at wrong price.

---

## B — No-Live-Order Containment

### Test 5 — S3 Never Creates Live Order

**What to check:** Scan output with `strategy_classification = S3_PAPER_SHADOW` never routes to order router.

**Pass condition:** Order router function returns None or logs to paper ledger only when classification is S3_PAPER_SHADOW.

**Fail condition:** Any DNSE API call or broker order object with `strategy_classification = S3_PAPER_SHADOW` as source.

**Code path:** Order router must check `strategy_classification` before routing.

---

### Test 6 — S3 `NEW_S3_SHADOW` Never Maps to Live Broker Order

**What to check:** `final_action = NEW_S3_SHADOW` produces a paper ledger entry only — never a broker order.

**Pass condition:** Only `s3_shadow_paper_trades.csv` is written. No broker API called.

**Fail condition:** Broker order created with `action = NEW_S3_SHADOW` as trigger.

---

### Test 7 — S3 `S3_SHADOW_HOLD` Never Maps to Live Broker Order

**What to check:** `final_action = S3_SHADOW_HOLD` produces no action at broker layer.

**Pass condition:** No broker API called for S3_SHADOW_HOLD rows.

**Fail condition:** Any broker call triggered by S3_SHADOW_HOLD.

---

### Test 8 — S3 `S3_SHADOW_EXIT` Only Updates Paper Ledger

**What to check:** `final_action = S3_SHADOW_EXIT` updates `s3_shadow_paper_trades.csv` and `s3_shadow_positions.csv` only.

**Pass condition:** Only paper files updated. No live order placed.

**Fail condition:** Broker sell order placed based on S3_SHADOW_EXIT signal.

---

### Test 9 — No DNSE Route for S3

**What to check:** `strategy_classification = S3_PAPER_SHADOW` is explicitly blocked in DNSE routing layer.

**Pass condition:** DNSE send function raises exception, returns early, or is structurally unreachable for S3_PAPER_SHADOW rows.

**Fail condition:** DNSE accepts S3_PAPER_SHADOW order without error.

---

### Test 10 — S3 Cannot Route via live_manual or live_auto Mode

**What to check:** Even if execution mode is set to `live_manual` or `live_auto`, S3 signals are not routed.

**Pass condition:** The mode check for S3 is prior to the live_mode check — S3 classification blocks routing regardless of mode.

**Fail condition:** `live_auto=True` overrides S3 classification guard.

**Code path:** `strategy_classification` check must be before mode check in order router.

---

## C — A3 Lead Rule and P&L Separation

### Test 11 — a3_s3_lead_5d: S3 Within 5 Bars Before A3

**What to check:** When S3 fires at bar N and A3 fires on same symbol at bars N+1 to N+5, `a3_s3_lead_5d = True`.

**Pass condition:** Field `a3_s3_lead_5d = True` appears for that A3 row.

**Test case:** HPG — S3 fires day 1, A3 fires day 4 (3 bars later). Expect `a3_s3_lead_5d = True`.

**Fail condition:** Field missing, always False, or always True regardless of timing.

---

### Test 12 — a3_s3_lead_5d Does Not Block A3

**What to check:** `a3_s3_lead_5d = False` coexists with `final_action = NEW_T1`.

**Pass condition:** A3 entry proceeds normally when `a3_s3_lead_5d = False`.

**Fail condition:** Any code path that sets `final_action = SKIP` or `WATCH_ONLY` because `a3_s3_lead_5d = False`.

---

### Test 13 — a3_s3_lead_5d Only Changes Sort Order

**What to check:** The only effect of `a3_s3_lead_5d = True` is ranking priority when multiple NEW_T1 signals exist on the same day.

**Pass condition:** Position size, T1/T2 logic, and stop levels are identical whether `a3_s3_lead_5d` is True or False.

**Fail condition:** Any size multiplier, T1 increase, or different exit rule applied when `a3_s3_lead_5d = True`.

---

### Test 14 — A3 and S3 P&L Tracked in Separate Files

**What to check:** A3 paper/live trades are logged to a different file than S3 shadow trades.

**Pass condition:**
- A3 trades → `data/decision/allocation_plan.json` or A3-specific ledger
- S3 shadow → `data/trading/live/s3_shadow_paper_trades.csv`

**Fail condition:** Any function receives both A3 and S3 trades in the same DataFrame without a `strategy` column separator.

---

### Test 15 — S3 P&L Does Not Appear in A3 Equity Curve

**What to check:** The A3 paper performance equity curve is computed from A3 trades only.

**Pass condition:** Any equity simulation function that reads from S3 ledger also uses a separate output path from A3 equity.

**Fail condition:** A3 equity curve function reads `s3_shadow_paper_trades.csv` directly or receives S3 rows without filtering.

---

## D — Schema and Data Integrity

### Test 16 — Phase35 Schema Has 47 Fields

**What to check:** `phase35_daily_scan_schema.csv` has exactly 47 data rows (header excluded).

**Pass condition:** Row count = 48 lines total (1 header + 47 field definitions).

**Fail condition:** 37 fields (Phase34) or any count other than 47.

---

### Test 17 — Sample CSV Rows All Have 47 Fields

**What to check:** Every row in `phase35_daily_scan_sample.csv` parses to exactly 47 fields.

**Pass condition:** `csv.DictReader` reads all rows with exactly 47 keys, no None keys.

**Fail condition:** Any row has 48 fields (shifted) or any key is None (extra comma causing field shift).

**Validation:** `phase35_csv_validation.py` must pass without assertion errors.

---

### Test 18 — Categorical Fields Have No Leading/Trailing Whitespace

**Categorical fields to check:** `final_action`, `strategy_classification`, `recommendation`, `liq_warn_T1`, `liq_warn_full`, `breadth_zone`, `s3_shadow_final_action`.

**Pass condition:** All non-blank values in categorical columns pass `value == value.strip()`.

**Fail condition:** Any leading space (e.g., ` NEW_S3_SHADOW`) or trailing space.

---

### Test 19 — strategy_classification Enum Only Contains Valid Values

**What to check:** All values of `strategy_classification` in sample are in the defined enum.

**Valid values:** `A3_PRODUCTION`, `PTS_SHADOW`, `S3_PAPER_SHADOW`, `S3_RESEARCH_ONLY`, `WATCH_ONLY`, `SKIP`.

**Pass condition:** No row has an undefined classification value.

**Fail condition:** Any row with `PARALLEL_PAPER_RESEARCH` (old GK5 classification removed from scan output) or typos.

---

### Test 20 — S3_GK5_max60_top100 Classification is FUTURE_RETEST_REQUIRED

**What to check:** `updated_final_candidate_classification.csv` has `S3_GK5_max60_top100` with classification `FUTURE_RETEST_REQUIRED`.

**Pass condition:** Row exists with classification = FUTURE_RETEST_REQUIRED.

**Fail condition:** Row still shows `PARALLEL_PAPER_RESEARCH` (stale — MAR=0.449 unverified).
