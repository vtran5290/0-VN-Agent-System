# Auto Account Readiness Ladder

Progression gates for automation. **Real capital: NO-GO** until explicit stage approval.

## Stage 0 — Manual discretionary execution

**Current stage.**

- Weekly HTML command center
- Manual cloud sanity check only
- Manual broker trades
- Paper accounts for validation only

## Stage 1 — Order-intent dry run

**Next stage.**

**Goal:** System produces intended orders; **sends none**.

**Unlock when:**

- 2–4 clean weekly cycles (positions + scan + report + review)
- No stale-data incidents without documented override
- All intended orders traceable to `final_action`
- No confusing suggested orders in dry-run CSV
- Manual override log used when cloud ≠ CSV

**Command:** `generate-order-intent` — see `ORDER_INTENT_DRY_RUN.md`

**Hard stop:** unsafe or ambiguous order suggestions; missing fail-closed behavior

## Stage 2 — Tiny real sandbox

**Future only.** Requires explicit user approval.

**Suggested constraints:**

- 20–50m VND capital
- No margin
- EOD only
- Max 3–5 positions initially
- Max 5–10% per position initially
- Max daily/weekly loss guard
- Kill switch documented and tested
- No intraday routing
- No S3 production
- No `live_auto` without separate review

**Unlock:** Stage 1 evidence + written approval + kill switch

## Stage 3 — Scaled private account

**Future only.**

- Larger private capital after 3+ months clean sandbox
- Hard stop on drawdown / ops breach

## Stage 4 — Copytrade / public account

**Future only.**

**Requirements:**

- 6–12 months verified real-money performance
- Max drawdown shown honestly
- Monthly report discipline
- Risk disclosure
- Broker/compliance route confirmed
- No return promises
- No managing client passwords/accounts directly

See `docs/business/COPYTRADE_AND_CONTENT_ROADMAP.md`.

## Stage 5 — Content / referral engine

**Future only.**

- Education first
- No auto-posted buy/sell calls
- Human approval before posts with tickers
- No guaranteed returns
- Show risks and drawdowns honestly

**Current status:** not active.

## Do not skip

Stage 0 → 1 → 2 → 3 → 4 → 5. No jump to copytrade or content automation without track record and compliance route.
