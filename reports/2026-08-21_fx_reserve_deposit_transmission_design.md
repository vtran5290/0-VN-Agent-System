# FX Pressure Easing → Reserve Rebuild → Deposit Rate Pivot — Approved Design

**Date:** 2026-08-21

**Status:** APPROVED FOR CURSOR IMPLEMENTATION

**Decision owner:** User

**Primary surface:** PM Regime Dashboard

**Secondary surface:** La Bàn T6 advisory mirror

## Decision

Implement one canonical, versioned `fx_reserve_deposit_transmission` contract inside the existing `data/research/rate_pivot_monitor.json`.

- PM Regime renders the full State 0–4 monitor, evidence ladder, confirmation checklist, falsifiers, implications, and historical context.
- La Bàn T6 renders a compact read-only mirror beside the GT1 liquidity assumption.
- The monitor is advisory and non-scoring on both surfaces.
- Do not create a La Bàn axis, structural signal, scenario input, weight input, hard invalidation, or regime-score input.

Existing cross-asset opportunity hard gates remain unchanged and out of scope:

> **“Main transmission blocked → search harder, not stop.”**

> **“What is moving that VNINDEX cannot currently express, and which listed Vietnamese company is the best proxy for that move?”**

## FACTS

### Current local monitor state

- `data/research/rate_pivot_monitor.json` is currently schema `rate_pivot_monitor_v1`, with `_meta.as_of = 2026-08-05` and overall label `FUNDING COST EASE WATCH`.
- Legacy C3 is marked `CONFIRMED`, but its current text mixes SBV central/ceiling, Vietcombank retail sell, parallel-market sell, and a secondary mid-market series. Those observations are not all economically comparable.
- Legacy C6 is marked `APPROACHING`, but its own notes contain an unresolved VPBank product/tier conflict and acknowledge that a large cut may be normalization from an unusual spike rather than clean cyclical easing.
- V2 currently records G1 FX `PASS`, G2 inflation `FAIL_IMPROVING`, P1 OMO `EARLY`, P2 deposit `MIXED`, and `v2_score = 0` / `GATED` as of 2026-07-16.
- The PM generator already reads `data/research/rate_pivot_monitor.json` through `scripts/reporting/generate_pm_regime_dashboard.py`.
- La Bàn currently has five structural axes. None is an appropriate canonical home for this cyclical FX/liquidity transmission.
- La Bàn GT1 (`GT1_khong_siet_thanh_khoan_keo_dai`) is the correct downstream contextual link. Its existing machine check remains unchanged.
- The current La Bàn engine snapshot is published with four valid structural axes. This design must not change its anchors, working values, observation count, axis count, scenarios, or publication state.

### Current external evidence classification

- **FACT / credible secondary:** the informal USD/VND premium has compressed materially and has at times been reported below bank selling levels. This is evidence that marginal informal USD demand weakened; it is not evidence that SBV bought FX. Source: [VnEconomy, 2026-08-10](https://vneconomy.vn/siet-rua-tien-qua-usdt-thu-hep-chenh-lech-gia-vang-usd-tu-do-lao-doc-duoi-26000-dong.htm).
- **FACT / primary:** Circular 25/2026/TT-NHNN was issued on 2026-06-22 and became effective 2026-07-01. Source: [Government legal-document portal](https://vanban.chinhphu.vn/?docid=218533&pageid=27160).
- **UNCONFIRMED PRIMARY:** an SBV-affiliated banking publication reports Decision 1743/QĐ-NHNN and 50% Treasury-deposit recognition for LDR from 2026-08-01 to 2028-07-31, but the original decision file has not been retrieved in the current research pack. Keep the local classification `SOURCE-SECONDARY`; do not silently promote it to primary-confirmed policy. Source: [Thời Báo Ngân Hàng](https://thoibaonganhang.vn/ngan-hang-nha-nuoc-chinh-thuc-nang-ty-le-tinh-tien-gui-kho-bac-nha-nuoc-vao-ldr-len-50-185695.html).
- **UNKNOWN:** current official interbank USD/VND spot series, disclosed SBV FX purchases, a current reliable reserve series, and a normalized exact-key multi-bank 6M/12M deposit panel are not yet available in the canonical monitor.

## ASSUMPTIONS

- The existing report suite remains the presentation architecture; no new dashboard is required.
- Phase 1 is a reporting/data-contract change. It does not build a new external data-ingestion pipeline.
- Existing daily deposit/FX automation may provide source observations, but it does not become a second state machine or competing source of truth.
- `rate_pivot_monitor.json` remains manually research-curated until a separately approved publisher/adapter is built.
- Historical episodes are supporting context only. No foreign or historical functional form or magnitude is assumed to transfer to present-day Vietnam.

## Architecture

```text
Official / credible source observations
                  ↓
Comparable-quote and freshness validation
                  ↓
data/research/rate_pivot_monitor.json
└─ fx_reserve_deposit_transmission (canonical contract)
                  ↓
      ┌───────────┴───────────┐
      ↓                       ↓
PM Regime full panel    La Bàn T6 mirror
(primary analysis)      (read-only advisory)
```

La Bàn must not pull or reinterpret raw FX data. Both surfaces consume the same normalized contract and display the same `current_state`, `as_of`, and `evidence_hash`.

## Canonical contract

Add this top-level object to the existing monitor without replacing unrelated fields:

```json
{
  "fx_reserve_deposit_transmission": {
    "schema": "fx_reserve_deposit_transmission_v1",
    "as_of": "2026-08-21",
    "headline": "FX PRESSURE EASING — POTENTIAL RESERVE-REBUILD SETUP",
    "current_state": {
      "id": 1,
      "label": "FX PRESSURE EASING",
      "status": "SETUP / APPROACHING",
      "evidence_class": "OBSERVATION",
      "confirmation_status": "NOT_CONFIRMED"
    },
    "deposit_thesis": {
      "headline": "PEAK-FORMING / STABILIZATION — NOT YET DOWNTREND CONFIRMED",
      "claim_class": "INFERENCE",
      "evidence_state": "WATCH / MIXED",
      "upgrade": "NONE"
    },
    "state_machine": [],
    "evidence_ladder": {
      "observation": [],
      "inference": [],
      "confirmation": []
    },
    "channels": {
      "fx": [],
      "external_flows": [],
      "reserve_liquidity": [],
      "bank_funding": []
    },
    "regulatory_funding_relief": {},
    "confirmation_checklist": [],
    "falsifiers": [],
    "historical_context": {},
    "implications": {},
    "scoring_effect": {
      "pm_regime": "NONE",
      "laban_axes": "NONE",
      "laban_scenarios": "NONE",
      "laban_weights": "NONE",
      "laban_regime": "NONE"
    },
    "evidence_hash": "sha256:<canonical-evidence-payload>"
  }
}
```

Every evidence row must carry:

- `variable_id`
- `label`
- `value` or `null`
- `unit`
- `as_of`
- `claim_class`: `FACT | INFERENCE | MARKET_CHATTER | UNCONFIRMED`
- `source_quality`: `PRIMARY | CREDIBLE_SECONDARY | SOURCE_SECONDARY | UNCONFIRMED`
- `freshness`: `FRESH | STALE | UNKNOWN`
- `status`: `PASS | PARTIAL | UNKNOWN | FAIL | NOT_COMPARABLE`
- `source_name`
- `source_url_or_path`
- `notes`

The `evidence_hash` is deterministic over state-relevant evidence, state, and `as_of`, with sorted keys and compact UTF-8 JSON. It is a parity/audit key, not a trading or scoring input.

## Evidence ladder

The UI must keep these statements separate:

### OBSERVATION

The informal USD premium has fallen. Calculate any premium only from comparable legs and comparable market basis: bid/bid or ask/ask. A parallel bid compared with a bank retail ask is `NOT_COMPARABLE`.

### INFERENCE

Banks may accumulate excess USD liquidity, which may give SBV room to purchase FX and rebuild reserves.

### CONFIRMATION

Confirmation requires evidence that SBV bought FX or reliable reserve estimates increased, followed by VND liquidity improvement and lower interbank funding pressure.

No renderer may combine these into one unqualified sentence.

## State machine

| State | Label | Minimum evidence |
|---:|---|---|
| 0 | FX PRESSURE | Informal premium positive/elevated; formal USD/VND pressured; reserve rebuilding difficult. |
| 1 | FX PRESSURE EASING | Informal premium falls materially/turns negative; formal USD/VND stops deteriorating. Current evidence is closest to this state. |
| 2 | RESERVE-REBUILD SETUP | State 1 persists; formal/interbank USD/VND is stable; real USD availability is evidenced through net flows and credible commercial-bank supply exceeding demand. |
| 3 | RESERVE REBUILD / LIQUIDITY TRANSMISSION CONFIRMED | SBV FX purchases or credible reserve increase; associated non-sterilized VND injection; O/N and 1W VND interbank liquidity ease. |
| 4 | DEPOSIT-RATE PIVOT CONFIRMED | Big-4 6M/12M rates decline; Tier-2/private banks follow; funding remains stable despite continued credit growth. |

Promotion rules:

- No skipped states.
- All required legs for the next state must be fresh and confirmed.
- `UNKNOWN`, stale data, market chatter, secondary-only inference, historical analogy, or a narrative count cannot promote a state.
- FDI, remittances, trade balance, or portfolio flow alone do not prove net commercial-bank USD surplus.
- An SBV FX purchase followed by full sterilization does not confirm VND-liquidity transmission.
- Promotions, different products, different depositor tiers, or a one-bank cut do not confirm State 4.

Downgrade rules:

- Downgrade when several material falsifiers co-occur or when evidence previously required for the current state is invalidated.
- A stale decisive leg renders `UNKNOWN / STALE`; narrative text cannot preserve a higher state.

## Regulatory versus monetary liquidity

Render these as parallel, economically distinct channels:

```text
Regulatory funding relief
  LDR treatment / funding-rule changes

Actual monetary liquidity creation
  SBV buys FX → pays VND → interbank liquidity improves
```

Regulatory relief may reduce marginal funding pressure, but it is not an SBV VND injection and cannot advance the reserve-transmission state on its own.

## Monitoring variables

### FX

1. Free-market USD/VND
2. Official/interbank USD/VND
3. SBV central/reference rate
4. Comparable-leg free-market premium/discount

### External flows

5. Trade balance
6. FDI disbursement
7. Foreign portfolio flows
8. Remittances
9. Balance-of-payments proxies

### Reserves and VND liquidity

10. SBV FX purchases
11. FX reserve estimates
12. OMO/SBV liquidity operations
13. O/N and 1W VND interbank rates

### Bank funding

14. Big-4 6M/12M deposit rates
15. Tier-2 6M/12M deposit rates
16. Deposit growth versus credit growth
17. LDR
18. System/bank NIM trajectory

Missing values remain `null`/`UNKNOWN`; no proxy silently becomes a reported series.

## Confirmation checklist

Track these nine rows with `PASS | PARTIAL | UNKNOWN | FAIL`:

1. Free-market premium compressed/negative for multiple weeks
2. Interbank USD/VND stable or falling
3. No renewed FX stress despite external shocks
4. Evidence of SBV FX purchases/reserve rebuilding
5. O/N and 1W VND liquidity materially improving
6. Big-4 deposit-rate increases stopping
7. Big-4 6M/12M rates declining
8. Tier-2 banks following
9. Credit growth remaining strong without renewed funding stress

Display-only interpretation:

- 0–2: noise/early signal
- 3–4: setup strengthening
- 5–6: transmission becoming credible
- 7–9: substantially confirmed

This count does not mechanically alter the existing Rate Pivot V2 score, PM Regime score, La Bàn state, or state-machine promotion.

## Falsifiers

- Free-market USD rebounds sharply.
- Interbank USD/VND resumes depreciation.
- DXY, oil, or global-risk shock renews dollar demand.
- SBV must sell rather than buy FX.
- VND interbank rates remain elevated.
- Banks continue raising 6M/12M deposit rates.
- Deposit growth remains materially below credit growth.
- Treasury deposits fall sharply as public-investment disbursement accelerates.
- Inflation/FX constraints prevent accommodation.

Several simultaneous falsifiers override historical analogy and downgrade the monitor.

## PM Regime rendering

The existing `Rate Pivot Monitor` remains the primary location. Add:

- headline/status card;
- State 0–4 ladder;
- Observation/Inference/Confirmation columns;
- four evidence-channel groups;
- separate regulatory-funding-relief panel;
- confirmation checklist and falsifiers;
- first- through fourth-order banking implications;
- brief equity implications without stock recommendations;
- collapsed historical-context note.

Add only a compact Macro Pulse badge: `FX → Liquidity: STATE 1 · NOT CONFIRMED`.

Correct the existing V2 binding-constraint callout: when G1 passes and G2 fails, the callout must identify G2 inflation—not G1 FX—as the binding gate.

## La Bàn rendering

Add a compact block at the top of T6, beside/contextually before GT1:

```text
FX–LIQUIDITY TRANSMISSION
State 1 · Positive-marginal · Not confirmed

Observation: informal FX pressure easing
Inference: reserve-rebuild capacity may improve
Confirmation: absent
GT1 impact: monitoring only
```

The La Bàn builder must run the engine first, then load/normalize the transmission contract solely for rendering. Do not pass the contract into `run_engine()` or persist it in `laban_axis_state.json`, `vn_structural_signals.json`, scenario files, frame logs, or engine snapshots.

## Historical context

- A collapsing/negative informal premium may accompany inflows, reserve accumulation, lower dollarization, and improving VND confidence. The spread is an indicator/symptom, not the cause of equity returns.
- 2006–07 also involved WTO accession, large foreign inflows, rapid credit growth, listings expansion, and speculation.
- 2012 is the cleaner analogy for the FX-confidence-reserves-monetary-easing transmission.
- Historical analogy is supporting commentary only and is excluded from trigger logic.

## Bank and equity implications

### First order

- Potentially more VND liquidity
- Lower interbank funding pressure

### Second order

- Lower marginal need to raise deposits
- Lower cost-of-funds pressure
- NIM stabilization

### Third order

- Credit can remain strong with less near-term funding stress
- Big-4 pricing may transmit through the system

### Fourth order / residual risk

- If credit continues to outgrow genuine deposits, relief may postpone rather than eliminate the funding gap.
- Constraints may migrate toward CAR, renewed FX pressure, inflation, or asset quality.

Equity display may mention banks, leveraged domestic sectors, and broader market liquidity. It must not create a stock recommendation from this signal.

## Old state → new state

| Surface | Old | Approved new state |
|---|---|---|
| FX reserve/deposit transmission | Absent | State 1 · SETUP/APPROACHING · NOT_CONFIRMED |
| Legacy C3 FX criterion | CONFIRMED | APPROACHING until a fresh comparable-leg formal-market observation is available |
| Legacy C6 deposit criterion | APPROACHING | WATCH because exact-key product/tier evidence is unresolved |
| V2 P2 deposit signal | MIXED | MIXED |
| V2 overall | GATED / score 0 | No change |
| PM overall regime | Existing state/score | No change |
| La Bàn axes/weights/regime | Existing values | No change |

## RISKS

- The working tree is heavily dirty. Several relevant files are already modified or untracked. Cursor must inspect and preserve existing content; no file replacement or broad formatting pass is allowed.
- `rate_pivot_monitor.json`, `laban_engine.py`, and relevant tests are currently untracked. `laban_render.py` and generated PM HTML already contain user changes.
- Current FX observations have quote-leg and market-basis mismatches.
- The current deposit panel has product/tier/source conflicts and cannot support a confirmed downtrend.
- SBV purchase and reserve data may remain unavailable; the correct output is `UNKNOWN`, not inferred confirmation.
- Adding a La Bàn render dependency before engine computation could contaminate structural output; ordering and invariance tests are mandatory.

## Acceptance criteria

1. PM and La Bàn render the same `state`, `as_of`, and `evidence_hash`.
2. Current rendered state is State 1 / `NOT_CONFIRMED`.
3. Missing commercial-bank FX-supply evidence blocks State 2.
4. Missing SBV purchase/reserve evidence blocks State 3.
5. Unchanged/non-comparable deposit observations block State 4.
6. LDR relief alone changes no transmission state.
7. No state can be skipped.
8. Malformed or stale contract renders `UNKNOWN / STALE`; no narrative fallback promotes it.
9. La Bàn anchors, working values, axes, scenarios, hard invalidations, and regime state are identical before and after the rendering change.
10. PM overall regime state/score and Rate Pivot V2 score remain unchanged.
11. Historical analogy appears only in supporting commentary.
12. No A3/S3/OMS, `final_action`, signal math, backtest parameter, DNSE, `live_auto`, or real-capital path is touched.

## ACTIONS

Cursor should implement the accompanying plan using small TDD patches, render both reports, run the targeted and full reporting tests, and return a review pack listing files changed/not touched, checks, residual data gaps, old→new states, and confirmation that La Bàn/PM regime scores did not change.

**Next action:** Cursor implements `reports/2026-08-21_fx_reserve_deposit_transmission_implementation_plan.md` and returns a dated `CursorDone` review pack for ChatGPT verification.
