# External Monetary Constraint Integration — Approved Design

**Date:** 2026-08-22  
**Status:** APPROVED FOR IMPLEMENTATION  
**Decision owner:** User  
**Primary surface:** PM Regime Dashboard  
**Secondary surfaces:** La Bàn T6 and Weekly Consolidated Global Macro/Fed-Rates  
**Daily intake:** Existing ChatGPT deposit-rate/FX daily workflow

## Decision

Extend the existing canonical `fx_reserve_deposit_transmission` contract in
`data/research/rate_pivot_monitor.json`. Add one nested
`external_monetary_constraint` object and render it through existing report
sections. Do not create a standalone “bond war” report, La Bàn axis, scoring
engine, or competing state machine.

The monitor answers one question:

> Is the external monetary environment opening or closing SBV policy room?

The required live causal test is:

```text
US long-end / JPY
  → global USD and liquidity pressure
  → USD/VND
  → SBV FX action and reserve capacity
  → VND liquidity
  → deposit-rate pivot
  → bank NIM and credit conditions
  → VN equity regime
```

The chain is a transmission mechanism, not a deterministic forecasting rule.

## FACTS

- PM Regime already renders the full FX→reserve→VND-liquidity→deposit-rate
  monitor from `rate_pivot_monitor.json`.
- La Bàn already renders a non-scoring T6 mirror from the same normalized
  contract after the structural engine has run.
- The existing US Fiscal Stress pipeline already tracks US 2Y/10Y/30Y yields,
  a 10Y term-premium proxy, 10Y/30Y Treasury auctions, and selected FRED inputs.
  Its current published state is `NOT_RUN`; its fiscal-stress score is not an
  admissible substitute for this transmission monitor.
- Weekly Consolidated already has Global Macro and Fed/Rates sections.
- The reusable ChatGPT daily deposit-rate prompt is the existing research
  intake surface for deposit, FX, and source-index work.
- The current FX-reserve-deposit state is State 1 / `NOT_CONFIRMED`, and both PM
  and La Bàn explicitly have no scoring effect from this advisory contract.

## ASSUMPTIONS

- The user-specified initialization is authoritative until a later daily run
  supplies fresher decision-grade evidence.
- Missing market data remains `null` / `UNKNOWN`; initialization is labeled as
  an operator state, not fabricated market evidence.
- Existing FRED/Treasury data may populate evidence rows when fresh, but this
  implementation does not silently activate or rescore the US Fiscal Stress
  engine.
- Weekly Consolidated will display a compact summary from the same canonical
  contract rather than maintain another score or narrative.
- Daily search results require human/research validation before the canonical
  monitor is promoted.

## Architecture

```text
Primary/official market data + dated news/search developments
                         ↓
Existing daily ChatGPT deposit/FX workflow
  - four mandatory search buckets
  - intervention/fundamentals classification
  - alert evaluation
  - 3–5 item causal synthesis
                         ↓
data/research/rate_pivot_monitor.json
└─ fx_reserve_deposit_transmission
   └─ external_monetary_constraint
                         ↓
      ┌──────────────────┼──────────────────┐
      ↓                  ↓                  ↓
PM Regime full     La Bàn T6 mirror   Weekly compact
analysis            non-scoring        summary
```

All three report surfaces consume the same normalized state, `as_of`, and
`evidence_hash`. La Bàn and Weekly Consolidated do not reinterpret raw
headlines or market observations.

## Canonical contract extension

Add the following nested shape without removing current State 0–4 content:

```json
{
  "external_monetary_constraint": {
    "schema": "external_monetary_constraint_v1",
    "as_of": "2026-08-22",
    "state": {
      "code": "AMBER",
      "label": "PRESSURE BUILDING",
      "display": "AMBER / WATCH",
      "basis": "OPERATOR_INITIALIZATION",
      "confirmation_status": "WATCH"
    },
    "pressure_direction": "BUILDING",
    "transmission_status": "NOT_YET_TRANSMITTED",
    "policy_vs_fundamentals": {},
    "channels": {},
    "alert_rules": [],
    "daily_synthesis": {},
    "causal_chain": [],
    "market_implications": {},
    "scoring_effect": {
      "pm_regime": "NONE",
      "laban_axes": "NONE",
      "laban_regime": "NONE",
      "weekly_regime": "NONE"
    }
  }
}
```

The outer transmission contract advances from schema v1 to v2. The shared
normalizer must accept v2, validate the nested monitor, fail closed to
`UNKNOWN`, and include the nested monitor in the deterministic evidence hash.

## State taxonomy

Use the existing green/amber/red display language. Do not add a parallel
numeric score.

| State | Display | Interpretation |
|---|---|---|
| GREEN | SUPPORTIVE | External conditions support SBV flexibility and the domestic deposit-rate pivot thesis. |
| AMBER | PRESSURE BUILDING / WATCH | External pressure may delay reserve rebuilding and deposit-rate easing. |
| RED | EXTERNAL CONSTRAINT | External macro is actively constraining SBV easing and may invalidate near-term pivot assumptions. |
| UNKNOWN | UNKNOWN | Evidence is missing, stale, malformed, or internally inconsistent. |

Initialize `AMBER / WATCH`. This does not override the current State 1 FX
pressure-easing observation because external pressure has not yet been shown
to transmit into worsening USD/VND or confirmed SBV defense.

## Policy intervention versus fundamentals

Every relevant development must be classified as one of:

- `PRICE_INTERVENTION`: Treasury buybacks, Japan FX intervention, or liquidity
  operations intended to alter market price/liquidity.
- `FUNDAMENTAL_CHANGE`: inflation, fiscal path, growth, Fed stance, BOJ rates,
  Japanese wages/trade/current account, or other supply-demand fundamentals.
- `VERBAL_INTERVENTION`: official warning or guidance without confirmed market
  action.
- `MARKET_CHATTER`: positioning, options, or unattributed intervention claims.

Price intervention without changed fundamentals is temporary relief, not a
regime change. Treasury buybacks are not QE. Japan buying JPY is not by itself
a durable JPY bull regime.

## Required monitoring variables

### US long-end and liquidity

US 2Y, 10Y, and 30Y; 2s10s and 10s30s; real yields; breakeven inflation;
term-premium proxies; auction bid-to-cover, indirect share, tail/stop-through;
refunding/issuance; buybacks; Fed balance sheet and QT/QE; TGA; RRP; 30Y
mortgage rate. Prefer 1D alerts plus 5D, 20D, and 3M trends/range breakouts.

### Japan and JPY

USD/JPY; distance to 160, recent highs, and prior intervention zones; JGB 10Y
and 30Y; BOJ/MOF signals; verbal and confirmed intervention; disclosed size;
options skew/risk reversals; speculative positioning; CPI; wages; current
account; trade balance; US–Japan rate differential.

### Global FX to Vietnam

DXY; CNH; Asian/EM FX; USD/VND interbank; bank retail bid and ask; free-market
bid and ask; comparable-leg premium/discount; SBV reference rate; SBV FX
action; reserves; trade balance; FDI disbursement; portfolio flows; remittances.

Free-market premium calculations must compare bid/bid or ask/ask. A
free-market bid versus bank retail ask is `NOT_COMPARABLE`, not an FX premium.

### Bank funding and transmission

Deposit-versus-credit gap; LDR and regulatory funding relief; Treasury-deposit
treatment; O/N and 1W VND interbank rates; SBV OMO; reserve-rebuild capacity;
Big-4 and Tier-2 6M/12M deposit rates; inflation; credit-growth pressure; NIM;
CAR; liquidity; asset quality.

The reported 20%→50% Treasury-deposit treatment remains
`MARKET_CHATTER / UNCONFIRMED_PRIMARY` until the original SBV document is
retrieved.

## Alert rules

Store declarative rules and report their triggered/not-triggered/unknown state:

- US 10Y or 30Y: ≥15bp in one day or ≥30bp in five trading days.
- Major failed Treasury auction.
- Material Treasury buyback-policy change.
- Fed QT/QE regime change.
- USD/JPY crosses 160 or the previous intervention high.
- Confirmed Japanese intervention, 2% one-day JPY move, or coordinated US–Japan
  action.
- USD/VND reaches a new 3M high.
- Comparable-leg free-market premium expands sharply.
- Confirmed SBV FX buying/selling or credible material reserve change.
- Big-4 6M/12M rate change, multiple Tier-2 banks moving together, O/N VND
  spike, or material LDR/funding-rule change.

Unknown data cannot trigger or clear an alert.

## Daily search and synthesis

Extend the existing reusable daily prompt with four mandatory buckets:

1. US Treasury / bond market.
2. Japan / yen.
3. Global FX transmission to Vietnam.
4. Vietnam bank funding / deposit-rate pivot.

Each run must search for new developments as well as current levels. Preferred
sources are the US Treasury, Federal Reserve, New York Fed, FRED, Japan MOF,
BOJ, SBV/Government legal portals, NSO/customs, and official bank rate tables.
Reuters, FT, Nikkei, Bloomberg/WSJ when accessible, and credible bank research
are secondary sources.

Output contract:

```text
EXTERNAL PRESSURE: EASING | NEUTRAL | BUILDING | STRESS
EVIDENCE: maximum 3–5 strongest developments
TRANSMISSION TO VIETNAM: SUPPORTS | NO CURRENT EFFECT | WEAKENS
CHANGE VS PREVIOUS DAY: meaningful deltas only
ALERTS: triggered rules only, plus material UNKNOWN gaps
```

The synthesis must explicitly test every link in the causal chain and state
where transmission has or has not occurred. It must not dump unrelated
headlines.

## PM Regime rendering

PM Regime is the full analytical surface:

- Macro & Market Pulse: compact `External Monetary Constraint · AMBER/WATCH`
  badge beside the existing FX→Liquidity badge.
- Existing Rate Pivot Monitor: add the external state, causal-chain strip,
  US/Fed-Rates, JPY, VN FX, policy-versus-fundamentals, alert, daily-synthesis,
  deposit-pivot, and NIM/credit sections.
- Regime header/summary: one context sentence stating whether external
  conditions support or constrain the current regime. It is a confidence note,
  not a score input.
- Existing DXY historical-cycle material remains historical context and cannot
  drive the live state.

## La Bàn rendering

Extend the existing T6 mirror only:

```text
EXTERNAL MONETARY CONSTRAINT
AMBER / WATCH · transmission not yet observed

US long-end / JPY → USD pressure → USD/VND → SBV room
Current VN FX state: pressure easing
Reserve rebuild: not confirmed
GT1 / deposit pivot impact: confidence constrained; monitoring only
```

The external block must be loaded after `run_engine()` and never enter La Bàn
axes, weights, scenarios, hard invalidations, structural observations, or
regime score.

## Weekly Consolidated rendering

Add one compact block under the existing Global Macro + Fed/Rates material:

- external state and direction;
- strongest weekly delta or 3–5 development synthesis;
- Vietnam transmission status;
- deposit/NIM implication;
- change from the prior observation.

The weekly surface must show the same state/date/hash and must not create a
weekly score.

## Market implications

When pressure eases, display possible support for banks, brokers, leveraged
domestic cyclicals, rate-sensitive equities, and broad valuation/liquidity.
When pressure rises, display risk to high-LDR/funding-sensitive banks,
leveraged sectors, and speculative liquidity trades.

These are contextual sensitivities only. The indicator cannot produce an
automatic stock recommendation.

## Initial state

| Monitor | Before | Approved initial state |
|---|---|---|
| Global Long-End / FX Pressure | Absent | AMBER / WATCH |
| VN FX | FX PRESSURE EASING | unchanged |
| Reserve rebuild | NOT_CONFIRMED | unchanged |
| Deposit rate | PEAK-FORMING / STABILIZATION | unchanged |
| PM Regime score/label | Existing | unchanged |
| La Bàn axes/weights/regime | Existing | unchanged |

No wholesale regime upgrade is permitted from this initialization.

## Testing and verification

- Validator accepts schema v2 and fails closed on malformed external state.
- All required US, Japan, Vietnam FX, and bank-funding variable IDs exist.
- All alert rules exist and unknown data cannot fire them.
- Policy intervention and fundamentals are rendered separately.
- Comparable-leg methodology is explicit; mismatched FX legs are rejected.
- PM contains full causal synthesis and the AMBER badge.
- La Bàn and Weekly show the same state/date/hash as PM.
- La Bàn engine inputs/outputs and PM regime score remain invariant.
- Daily prompt contains all four search buckets, source hierarchy, distinction
  among official/verbal/chatter intervention, and causal synthesis contract.
- Historical analogies and stock recommendations are absent from trigger logic.

## RISKS

- The VN Agent worktree is heavily dirty; only named task files may be edited.
- Weekly report wiring may have both Markdown and HTML render paths; both must
  consume the same summary or one must be explicitly left out and disclosed.
- Market levels may be unavailable or stale. The correct state for a missing
  evidence row is `UNKNOWN`, not a carried-forward value presented as current.
- Initial AMBER is an operator-authorized watch state, not a claim that all
  listed market conditions have been freshly observed.
- Existing generated reports can change mtimes or unrelated embedded content;
  targeted diffs and invariance tests are mandatory.

## ACTIONS

Implement with small TDD patches, preserve current non-scoring architecture,
regenerate only relevant report targets, and produce a dated review pack with
files changed/not touched, variables, alerts, old→new states, score invariance,
data sources, and unresolved gaps.

**Next action:** write and execute the file-level implementation plan after the
user reviews this design specification.
