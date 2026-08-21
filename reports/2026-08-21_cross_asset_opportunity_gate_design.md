# Cross-Asset Opportunity Transmission Gate — Design Specification

**Date:** 2026-08-21  
**Status:** DRAFT FOR USER REVIEW — NO PRODUCTION IMPLEMENTATION  
**Domain:** Vietnam investment research / La Bàn VN  
**Decision owner:** V  

## Objective

Add a mandatory, auditable last-mile workflow from a material global asset or macro shock to Vietnam-listed research candidates, especially when VNINDEX cannot express the move. The upgrade must prevent premature stopping at a blocked broad-market transmission while remaining completely separate from La Bàn scenario weights, A3/S3, `final_action`, sizing, and OMS.

## FACTS

- The current La Bàn engine is display/advisory-only and computes structural scenario weights from scenarios, structural signals, axes, frame log, kill conditions, and assumptions.
- The current engine has no general shock → blocked VNINDEX transmission → Vietnam-listed proxy instrument.
- A shock-specific multi-order implementation exists for Hormuz/energy, but it ends at a sector map rather than a general listed-company coverage gate.
- `laban_advisory_links.json` establishes a safe precedent: research context is loaded separately, has no scoring effect, and is joined only at render time.
- The current ThemePack candidate output can become a backtest universe through `--candidates`; therefore cross-asset research candidates must never be written to ThemePack candidate paths.
- FireAnt is the required first source for Vietnam-listed universe, company, price, volume, technical, and liquidity data.
- The claim that PNJ repriced because of gold is not established by the inspected source pack. It remains a post-hoc hypothesis until the price window, benchmark, company exposure, and causal evidence are verified.

## ASSUMPTIONS

- “Proceed” approves the recommended semantics: a failed cross-asset gate blocks recommendation/action finalization but does not block or alter La Bàn macro/scenario publication.
- Version 1 is an operator-maintained, machine-validated sidecar. It does not auto-fetch global market data.
- “Best proxy” means the best defensible research candidate among qualified rows, never a BUY instruction.
- A material shock can be activated by a standardized/percentile move where data exist or by a documented regime-relevant event where they do not.

## Non-negotiable hard gates

The following strings are exact UTF-8 policy constants. Tests must compare them byte-for-byte.

> “Main transmission blocked → search harder, not stop.”

> “What is moving that VNINDEX cannot currently express, and which listed Vietnamese company is the best proxy for that move?”

### Behavioral meaning

1. For every active material shock, the second question must have an explicit answer object.
2. If `main_transmission_status == BLOCKED`, the first sentence activates a mandatory alternative-transmission branch.
3. Missing mechanism, evidence, alternative branch, universe denominator, scan manifest, or answer produces `FAIL_CLOSED`.
4. `FAIL_CLOSED` renders `COVERAGE GAP — further ticker scan required` and sets `recommendation_gate = BLOCKED`.
5. `FAIL_CLOSED` does not alter or block scenario weights or macro publication.
6. The question must not force a ticker. A valid answer can be `NO DEFENSIBLE PROXY` only after a complete, documented universe scan.

## Scope

### IN

- Active-shock record and FACT/INFERENCE trace.
- Multi-order mechanism and adverse-order branch.
- Main VN transmission status and blockers.
- Cross-asset substitution search.
- Full Vietnam-listed universe manifest and coverage gaps.
- Direct, indirect, substitution, and listed-proxy candidates.
- Fundamental sensitivity, technical, valuation, liquidity, and adverse-risk checks.
- Research ranking and “already extended” protection.
- Post-mortem learning loop with post-hoc safeguards.
- Compact mandatory La Bàn display and machine-readable status.

### OUT

- Changes to `laban_engine.py` weight logic, scenario maps, axes, signatures, or structural signals.
- A3/S3/backtest parameter changes, `final_action`, OMS, broker submission, real capital, sizing, targets, stops, BUY/SELL instructions.
- Automatic promotion of a discovered candidate into any trading or backtest universe.
- Automatic acceptance of post-mortem mappings as decision-grade.

## Architecture alternatives

### Approach A — Put proxy logic inside `laban_engine.py`

**Trade-off:** strongest apparent integration, but it mixes tactical opportunity discovery with the frozen 10Y/36M scenario engine and creates post-hoc scoring contamination.

**Decision:** REJECT.

### Approach B — Non-scoring sidecar validated by the builder

**Trade-off:** mandatory, auditable, testable, and visible in La Bàn while remaining one-way and non-scoring. Requires a small sidecar schema, validator, mapping registry, renderer block, and tests.

**Decision:** RECOMMENDED.

### Approach C — Standalone external research report linked from La Bàn

**Trade-off:** strongest isolation and useful for a shadow pilot, but too easy for daily/weekly workflow to skip and cannot reliably enforce the hard gates.

**Decision:** PILOT/ARCHIVE ONLY, not the durable design.

## Recommended component design

### 1. Current-run sidecar

Create `data/decision/laban_cross_asset_gate.json`.

Top-level contract:

- `schema`, `version`, `as_of`.
- `policy_constants`: both exact hard-gate strings.
- `effects`: `weights`, `state`, `coverage`, `confidence`, `universe`, `final_action`, `oms` must all equal `NONE`.
- `status`: `NOT_APPLICABLE | COMPLETE_CANDIDATES | COMPLETE_NO_DEFENSIBLE_PROXY | FAIL_CLOSED`.
- `recommendation_gate`: `OPEN | BLOCKED | NOT_APPLICABLE`.
- `active_shocks[]`.
- `coverage_summary`.
- `warnings[]`.

Each active shock contains:

- `shock_id`, asset/variable, direction, magnitude, timeframe, activation basis, as-of, source.
- `facts[]`: stable IDs, statements/values, dates, source, source quality.
- `inferences[]`: stable IDs, supporting fact IDs, order 1–4, mechanism, persistence, falsifier.
- `main_vn_transmission`: `OPEN | BLOCKED | PARTIAL | UNKNOWN`, blockers, supporting IDs.
- `alternative_transmission`: categories checked, findings, missing branches, confirm/falsify evidence.
- `universe_scan`: source, as-of, eligible/scanned/excluded counts, exclusions, unmapped symbols, coverage gaps.
- `candidates[]`.
- `best_proxy_answer`: qualified symbol plus rationale, `NO DEFENSIBLE PROXY`, or `COVERAGE GAP`.

### 2. Persistent exposure-edge registry

Create `data/decision/laban_cross_asset_proxy_map.json`.

Each mapping is an auditable edge:

`asset/mechanism → exposure channel → Vietnam-listed company`

Required fields:

- asset/mechanism IDs and symbol.
- exposure type: `DIRECT | STRONG_INDIRECT | WEAK_PROXY | SUBSTITUTION`.
- company-exposure fact/source/as-of.
- adverse mechanism and falsifier.
- status: `ACTIVE | DRAFT_POST_HOC | RETIRED`.
- last verified date and staleness.

Post-mortem mappings enter as `DRAFT_POST_HOC`. Promotion to `ACTIVE` requires independent evidence and prospective confirmation; a missed event cannot immediately rewrite the decision-grade map.

### 3. Pure validator/evaluator

Create `scripts/reporting/laban_cross_asset_gate.py`.

Responsibilities:

- Validate exact policy constants and reject drift.
- Validate FACT → INFERENCE → candidate reference integrity.
- Enforce conditional blocked-transmission search.
- Enforce coverage denominator and manifest.
- Compute terminal status and `recommendation_gate` deterministically.
- Force stale/missing inputs to `FAIL_CLOSED` or `INSUFFICIENT DATA`.
- Force `technical_state = EXTENDED` to `EXTENDED — DO NOT CHASE`.
- Reject prohibited fields or semantics: BUY, SELL, sizing, target, stop, `final_action`, OMS, or automatic universe promotion.

The evaluator must not import or call La Bàn weight functions.

### 4. Builder integration

Modify `scripts/reporting/build_vn_structural_signals.py` only to:

1. Load and validate the sidecar and exposure registry before any output write.
2. Run the existing La Bàn engine without either cross-asset artifact.
3. Evaluate the cross-asset gate separately.
4. Pass the result only to the renderer.
5. Refuse all writes on invalid schema/reference integrity.
6. Permit macro/scenario publication when content is valid but `FAIL_CLOSED`; render the red blocked-recommendation state.

### 5. Rendering

Modify `scripts/reporting/laban_render.py` without adding a new tab:

- T1: one-line gate status strip so an active failure cannot be missed.
- T3: compact mandatory `MISSED-OPPORTUNITY PREVENTION` card containing large moves, main transmission, blocked branches, alternatives, listed proxies, early confirmation, extended names, and coverage gaps.
- Permanent banner: `CANDIDATE — NOT A BUY RECOMMENDATION`.
- Preserve the existing uncommitted Tariff Watch change exactly.

No shell, T5 array, scenario-weight, or axis-card change is required.

### 6. Workflow documentation

Update the current workflow documentation to make the following sequence mandatory:

`Event detection → Fact verification → Mechanism → Multi-order effects → Main VN transmission → Blocked-transmission test → Cross-asset substitution test → Vietnam listed-proxy universe scan → Fundamental sensitivity → Technical confirmation → Valuation → Risk/adverse-order check → Research ranking → Human review`

The terminal step is “Human review,” not an automated action.

## Candidate contract and false-positive controls

Each candidate requires:

- symbol and exposure type.
- linked mechanism/fact IDs.
- transmission directness and earnings sensitivity.
- timing and persistence.
- market-awareness state.
- technical state, as-of, and FireAnt source.
- liquidity state and source.
- valuation check or explicit `Unknown`.
- adverse-order risk and falsifier.
- research status.

Allowed research statuses:

- `EARLY — RESEARCH NOW`
- `WATCH FOR TRIGGER`
- `RESEARCH-READY — HUMAN REVIEW REQUIRED`
- `EXTENDED — DO NOT CHASE`
- `THESIS INVALID`
- `INSUFFICIENT DATA`

`ACTIONABLE` is deliberately not used because it can be misread as an order instruction.

A candidate cannot become the `best_proxy_answer` unless mechanism, company exposure, coverage, technical/liquidity, valuation or explicit valuation limitation, and adverse-order checks are present. Missing load-bearing evidence yields `INSUFFICIENT DATA`.

## Coverage policy

- The denominator must be an as-of full listed-universe snapshot, not `watchlist.txt` or an existing ThemePack.
- FireAnt is the first source. Record source method, universe date, symbols eligible, scanned, excluded, and exclusion reasons.
- Every excluded or unclassified potentially relevant symbol remains visible in `coverage_gaps`.
- A watchlist-only scan can never produce `COMPLETE_NO_DEFENSIBLE_PROXY`.
- If complete coverage cannot be demonstrated, use `COVERAGE GAP — further ticker scan required`.

## Mandatory acceptance tests

1. Both policy constants match exact UTF-8 bytes.
2. Every active shock has a `best_proxy_answer` object.
3. A blocked main transmission with an incomplete alternative branch returns `FAIL_CLOSED`.
4. Missing or stale shock, exposure, technical, liquidity, or coverage evidence cannot qualify a proxy.
5. Every inference references existing facts; every candidate references existing inferences/facts.
6. Incomplete universe coverage returns `FAIL_CLOSED` and blocks recommendation finalization.
7. A complete scan may return `COMPLETE_NO_DEFENSIBLE_PROXY` without forcing a ticker.
8. `technical_state = EXTENDED` forces `EXTENDED — DO NOT CHASE`.
9. Invalid schema/reference integrity exits non-zero before snapshot or HTML writes.
10. Changing only cross-asset artifacts changes only the opportunity rendering; La Bàn weight snapshot/hash remains identical.
11. No allowed field/status contains trading instructions or writes to candidate/backtest universes.
12. Existing idempotency, cold-start, kill-condition, T5 byte-hash, advisory-containment, and no-street-leak tests continue to pass.
13. Existing Tariff Watch rendering remains present and unchanged.
14. PNJ/gold is a hypothesis fixture: it tests discovery and fail-closed behavior, not historical causality or an investment conclusion.

## RISKS

- **Framework contamination:** mitigated by never passing sidecar data to `run_engine()`.
- **False exhaustiveness:** mitigated by a dated full-universe denominator and explicit coverage gaps.
- **Aggregate-flow fallacy:** “Where does capital go?” is treated as a hypothesis requiring confirming/falsifying evidence, not a fact.
- **Post-hoc overfitting:** missed-opportunity mappings remain `DRAFT_POST_HOC` until independently supported and prospectively observed.
- **Candidate-to-BUY drift:** prohibited fields, safe research statuses, human review, and no universe bridge.
- **Dirty-tree collision:** current La Bàn working state includes an uncommitted Tariff Watch change and untracked engine/test/report files. Implementation must patch the current bytes, never reset, overwrite, or assume Git HEAD is the whole source of truth.
- **Stale data:** missing or stale evidence fails closed rather than implying no opportunity.

## ACTIONS

After user approval of this specification:

1. Write a detailed implementation plan with exact patch order and rollback points.
2. Route the accompanying ReviewPack for final `APPROVE | REJECT | REDIRECT`.
3. Implement only after approval, beginning with tests and the non-scoring validator.
4. Run a shadow pilot; do not connect any candidate to trading or backtest universes.

**Next decision required from V:** approve or redirect this design before implementation planning begins.
