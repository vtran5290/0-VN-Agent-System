# VN TA Multi-Timeframe and Weekly Structural Support Implementation Plan

Date: 2026-08-26

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the VN TA skill and non-live FireAnt CLI with measured weekly MA-compression, structural-zone, role-reversal, absorption, weekly-close, RSI-reset, and scoring evidence.

**Architecture:** Keep the main skill as the routing and schema contract, place the full weekly doctrine in a progressively loaded reference, and implement observable evidence in focused CLI helpers. Preserve conservative unknowns for ambiguous Wyckoff and institutional-intent claims.

**Tech Stack:** Python 3, pandas, NumPy, pytest, Markdown agent skills, FireAnt OHLCV helper.

---

## FACTS

- Approved scope is skill + non-live CLI + tests.
- Existing monthly edits are user-compatible work and must be preserved.
- No live/prod trading files are authorized.

## ASSUMPTIONS

- Additive JSON fields are safer than renaming existing fields.
- Synthetic weekly fixtures provide deterministic verification without FireAnt network access.

## RISKS

- Threshold heuristics may appear more certain than the evidence warrants; every result must include counts or explicit `not_confirmed` states.
- Existing unrelated worktree changes must remain untouched.

## ACTIONS

### Task 1: Establish failing weekly evidence tests

**Files:**
- Create: `tests/test_vn_ta_weekly_structural_support.py`
- Modify: none

- [ ] **Step 1: Write failing tests for MA cluster width and classification**

```python
def test_weekly_ma_cluster_classifies_tight_confluence():
    result = _weekly_ma_cluster_from_values({"ma20": 61.25, "ma50": 61.35, "ma100": 60.60})
    assert result["width_pct"] < 2.0
    assert result["classification"] == "very_tight"
```

- [ ] **Step 2: Write a failing test for declining-cluster caution**

```python
def test_declining_cluster_is_not_automatically_bullish():
    weekly = make_weekly_fixture(trend="declining_cluster")
    result = _weekly_structural_assessment(weekly)
    assert result["ma_cluster"]["trend_quality"] == "declining_cluster_caution"
    assert result["score_breakdown"]["ma_confluence"] < 20
```

- [ ] **Step 3: Write failing tests for weekly-close success and failure**

```python
def test_weekly_close_inside_zone_survives_intrawweek_undercut():
    result = _classify_weekly_close_test(low=59.8, close=61.9, volume_ratio=0.8, zone_low=60.5, zone_high=62.0)
    assert result["state"] == "support_test_held"

def test_weekly_close_below_zone_on_expanding_volume_fails():
    result = _classify_weekly_close_test(low=59.4, close=59.5, volume_ratio=1.6, zone_low=60.5, zone_high=62.0)
    assert result["state"] == "support_failure"
```

- [ ] **Step 4: Run the focused tests and confirm they fail because the helpers do not exist**

Run: `python -m pytest tests/test_vn_ta_weekly_structural_support.py -q`

Expected: collection/import failure naming the missing weekly helpers.

### Task 2: Implement weekly indicators and MA compression

**Files:**
- Modify: `scripts/vn_ta_fireant_cli.py`
- Test: `tests/test_vn_ta_weekly_structural_support.py`

- [ ] **Step 1: Add RSI14, EMA10, and EMA20 to indicator computation**

Use Wilder RSI with average gains/losses and retain null when history is insufficient.

- [ ] **Step 2: Implement `_weekly_ma_cluster_from_values`**

Return selected MA values, mean, `width_pct`, classification (`very_tight`, `strong`, `moderate`, `weak`), and availability. Use the approved boundaries `<2`, `<4`, `<7`, and `>=7` percent.

- [ ] **Step 3: Implement slope evidence and declining-cluster caution**

Classify each available weekly MA as `up`, `flat`, or `down`; report `flat_or_rising` only when at least half are non-declining.

- [ ] **Step 4: Run focused tests**

Run: `python -m pytest tests/test_vn_ta_weekly_structural_support.py -q`

Expected: MA cluster tests pass; structural tests remain failing until Task 3.

### Task 3: Implement weekly structural assessment and score

**Files:**
- Modify: `scripts/vn_ta_fireant_cli.py`
- Test: `tests/test_vn_ta_weekly_structural_support.py`

- [ ] **Step 1: Build the candidate zone from available SMA20W/SMA50W/SMA100W**

Use the min/max cluster values with a small evidence band; expose the representative level as the cluster mean and never as an exact required hold.

- [ ] **Step 2: Measure horizontal market memory**

Count weekly body/close reactions, zone overlaps, and historical acceptance. Weight close/body observations more heavily than wick-only touches.

- [ ] **Step 3: Measure role reversal, base memory, and origin of markup conservatively**

Require an observable sequence for role reversal: pre-breakout closes below the zone, breakout close above it, and later retest/hold. Otherwise return `not_confirmed` and award no points.

- [ ] **Step 4: Measure weekly volume and effort-versus-result**

Compare down-week volume and spread with 20-week baselines; distinguish possible absorption, weak/no demand, unresolved, and support failure.

- [ ] **Step 5: Implement the approved 100-point weekly rubric**

Return exact category totals: MA confluence 20, horizontal pivot 20, role reversal 15, prior base/origin 15, volume/absorption 20, and momentum/invalidation 10. Derive the approved classification labels without filling unknown evidence.

- [ ] **Step 6: Implement weekly-close confirmation and invalidation**

Use closing evidence, volume expansion, and reclaim state. An isolated wick below the zone cannot by itself mark failure.

- [ ] **Step 7: Run all focused tests**

Run: `python -m pytest tests/test_vn_ta_weekly_structural_support.py -q`

Expected: all focused tests pass.

### Task 4: Integrate weekly evidence into the report schema

**Files:**
- Modify: `scripts/vn_ta_fireant_cli.py`
- Modify: `.agents/skills/source-command-vn-ta/SKILL.md`
- Test: `tests/test_vn_ta_weekly_structural_support.py`

- [ ] **Step 1: Add `weekly_structure`, weekly zone evidence, and weekly close tests to each ticker result**

Expose trend, range/base state, MA cluster, role reversal, volume/absorption, RSI reset, phase evidence, score, verdict, confirmation close, and invalidation close.

- [ ] **Step 2: Preserve top-level compatibility**

Keep existing `levels`, `trend_regime`, `volume_action`, `wyckoff`, `entry_quality`, `trade_plan_1_3m`, and integrity fields.

- [ ] **Step 3: Add partial-data tests**

Verify fewer than two available weekly MAs yields `not_available`, score components remain zero/not confirmed, and valid JSON shape is preserved.

- [ ] **Step 4: Run focused tests**

Run: `python -m pytest tests/test_vn_ta_weekly_structural_support.py -q`

Expected: all tests pass.

### Task 5: Add the weekly skill reference and routing

**Files:**
- Create: `.agents/skills/source-command-vn-ta/reference-weekly-structural-support.md`
- Modify: `.agents/skills/source-command-vn-ta/SKILL.md`
- Create: `.agents/skills/source-command-vn-ta/evals/evals.json`

- [ ] **Step 1: Add the full approved weekly doctrine**

Cover zones-not-lines, MA compression, horizontal pivots, role reversal, prior base, markup origin, weekly volume, weekly close priority, RSI reset, Wyckoff LPS/backup, score, verdict labels, and the VCB teaching case.

- [ ] **Step 2: Route weekly reviews to the reference**

The main skill must explicitly require reading the weekly reference for weekly support/resistance, base repair, LPS/backup, role reversal, MA compression, stock ranking, and screening requests.

- [ ] **Step 3: Update the JSON schema and narrative output contract**

Document the additive weekly fields and require `not confirmed` for ungrounded events.

- [ ] **Step 4: Check skill structure and encoding**

Run a YAML/frontmatter parse and scan for mojibake markers.

Expected: valid frontmatter, no replacement characters, and both references discoverable from the main skill.

### Task 6: Final verification

**Files:**
- Verify all modified files only

- [ ] **Step 1: Run syntax compilation**

Run: `python -m py_compile scripts/vn_ta_fireant_cli.py tests/test_vn_ta_weekly_structural_support.py`

Expected: exit code 0.

- [ ] **Step 2: Run focused tests**

Run: `python -m pytest tests/test_vn_ta_weekly_structural_support.py -q`

Expected: all tests pass.

- [ ] **Step 3: Run existing nearby tests if available**

Run the smallest relevant FireAnt/TA test set. Do not invoke the network.

- [ ] **Step 4: Inspect the exact diff**

Confirm no live/prod trading logic or unrelated user changes were modified.

- [ ] **Step 5: Report measured outcomes and residual limitations**

State test counts, data-source contract, heuristic limitations, and the concrete next decision.

Next action: execute Tasks 1–6 inline with test-first checkpoints.
