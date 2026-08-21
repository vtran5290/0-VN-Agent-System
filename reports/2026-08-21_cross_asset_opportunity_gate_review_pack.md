# ReviewPack — Cross-Asset Opportunity Transmission Gate

**Date:** 2026-08-21  
**Status:** REVIEW REQUIRED — NO PRODUCTION IMPLEMENTATION  
**Requested verdict:** `APPROVE | REJECT | REDIRECT`  

## Review question

Should La Bàn adopt a mandatory, non-scoring cross-asset sidecar that fails closed on incomplete transmission/proxy coverage, blocks only recommendation finalization, and leaves the frozen scenario engine and all trading paths untouched?

## FACTS

- The inspected workspace contains no general cross-asset flow-of-funds/listed-proxy instrument.
- Existing multi-order logic is shock-specific and does not enforce a full listed-company scan.
- The current La Bàn engine is deterministic and display/advisory-only.
- Existing advisory content is structurally separate from scoring inputs and joined only during rendering.
- The proposed gate fills a research-workflow gap; it is not a new structural axis or scenario signal.
- FireAnt is the required first source for Vietnam-listed market/company data.
- Current working state must be preserved: `scripts/reporting/laban_render.py` has an uncommitted Tariff Watch change, while several La Bàn engine/test/report files are currently untracked in the nested repository.

## ASSUMPTIONS

- “Proceed” approves the recommendation-boundary semantics stated below, but does not yet authorize production implementation before this written ReviewPack is approved.
- Version 1 remains operator-maintained and machine-validated; automated cross-asset data ingestion is a later, separately reviewed phase.
- “Best proxy” means a qualified research candidate, never a BUY/SELL instruction or automatic universe inclusion.

## User non-negotiables

These strings must remain verbatim and machine-tested:

> “Main transmission blocked → search harder, not stop.”

> “What is moving that VNINDEX cannot currently express, and which listed Vietnamese company is the best proxy for that move?”

Approved semantic assumption: `FAIL_CLOSED` blocks sector/ticker recommendation and research-action finalization, but does not block macro/scenario publication.

## Proposed design

Use a sibling, non-scoring sidecar rather than modify the La Bàn engine:

- Current-run artifact: `data/decision/laban_cross_asset_gate.json`.
- Persistent exposure registry: `data/decision/laban_cross_asset_proxy_map.json`.
- Pure validator/evaluator: `scripts/reporting/laban_cross_asset_gate.py`.
- Builder integration: load/validate separately; never pass to `run_engine()`.
- Renderer integration: T1 status strip and compact T3 `MISSED-OPPORTUNITY PREVENTION` card.
- Tests: exact hard-gate strings, fail-closed behavior, reference integrity, complete-universe coverage, no-chase enforcement, prohibited trading semantics, and frozen-snapshot invariance.

Full specification: `reports/2026-08-21_cross_asset_opportunity_gate_design.md`.

## Alternatives considered

1. **Engine-native proxy logic — REJECT.** Contaminates frozen structural scoring with tactical opportunity discovery.
2. **Validated non-scoring sidecar — RECOMMEND.** Mandatory, auditable, visible, one-way, and testable.
3. **External report only — PILOT ONLY.** Clean but too easy to skip and cannot enforce the hard gates reliably.

## Scope IN

- Material-shock record, FACT/INFERENCE trace, multi-order tree, blocked-transmission branch.
- Dynamic full-listed-universe coverage manifest.
- Direct/indirect/substitution proxy research candidates.
- Fundamental, technical, valuation, liquidity, adverse-risk, and no-chase checks.
- Post-mortem mapping loop with `DRAFT_POST_HOC` safeguards.

## Scope OUT / protected

- `laban_engine.py` weight logic, structural signals, scenario maps, axes, signatures, T5 tables.
- A3/S3, backtest parameters, `final_action`, OMS, broker paths, sizing, targets, stops, real capital.
- Automatic candidate promotion to trading/backtest universes.
- Any claim that PNJ/gold causality is already established.

## Key controls

- `effects.weights/state/coverage/confidence/universe/final_action/oms = NONE`.
- Invalid schema fails before any snapshot/HTML write.
- Active incomplete coverage renders `COVERAGE GAP — further ticker scan required`.
- A complete scan can return `NO DEFENSIBLE PROXY`; the hard question never forces a ticker.
- `EXTENDED` always becomes `EXTENDED — DO NOT CHASE`.
- `ACTIONABLE` is replaced by `RESEARCH-READY — HUMAN REVIEW REQUIRED`.
- New post-mortem mappings remain exploratory until independently supported and prospectively validated.

## Council record

- **Artifact seat:** `gpt-5.6-sol`, `xhigh`, read-only — verdict `REDIRECT`. Accepted: sidecar, no scoring leakage, complete-universe manifest, research-only statuses, snapshot invariance.
- **Framework seat:** `gpt-5.6-sol`, `max`, read-only — verdict `GAP`. Accepted: genuine missing pathway; engine-native implementation would create conflict; fail closed only at recommendation boundary.
- Same-family seats provide process independence, not provider independence.
- No files were changed by either seat.

## RISKS

- Material-shock activation is not yet calibrated across all asset classes; V1 therefore requires documented activation basis and uses standardized/percentile moves where available.
- Full-universe company-exposure data can be incomplete; coverage must remain explicit rather than silently inferred.
- “Capital goes elsewhere” can become an aggregate-accounting fallacy; alternative flows remain hypotheses until supported by direct or discriminating observations.
- Implementation touches a currently modified renderer; a reset or broad rewrite could destroy existing work.

## ACTIONS

Reviewer should answer:

1. Does the sidecar boundary adequately protect the frozen La Bàn engine?
2. Are the terminal states and fail-closed semantics correct?
3. Is replacing `ACTIONABLE` with `RESEARCH-READY — HUMAN REVIEW REQUIRED` acceptable?
4. Are a per-run sidecar plus a persistent mapping registry the minimum sufficient artifacts?
5. Are the acceptance tests sufficient to prevent scoring, trading, and false-exhaustiveness leakage?

**Next decision required from V:** `APPROVE`, `REJECT`, or `REDIRECT` this ReviewPack before implementation planning or production changes.
