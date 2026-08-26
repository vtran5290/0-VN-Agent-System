# VN TA Multi-Timeframe and Weekly Structural Support Design

Date: 2026-08-26

## FACTS

- The existing `source-command-vn-ta` skill now covers monthly, weekly, and daily hierarchy, but the approved weekly doctrine is not yet represented in a dedicated reference.
- The non-live `scripts/vn_ta_fireant_cli.py` currently fetches monthly, weekly, and daily OHLCV and seeds a monthly SMA50 candidate zone.
- Weekly MA compression, RSI14W, role-reversal evidence, weekly close validation, and the weekly 100-point score are not computed.
- Automated Wyckoff phase assignment is intentionally conservative and remains `unclear` without at least two independent confirming signals.
- Live trading logic, production signal generators, and backtest parameters are outside this change.

## ASSUMPTIONS

- FireAnt remains the first and only market-data source used by the CLI.
- A weekly structural candidate can be generated only when at least two of SMA20W, SMA50W, and SMA100W are available.
- Automated output must distinguish measured evidence from unconfirmed interpretation. Prior base, origin of markup, LPS, and role reversal receive points only when their observable heuristic is satisfied.
- Weekly close and body evidence has greater decision weight than isolated intraday wick penetration.
- JSON output remains backward-compatible at the top level; new weekly fields are additive.

## RISKS

- A tight cluster of steeply falling moving averages can be mistaken for bullish confluence. The implementation therefore reports a declining-cluster caution and withholds the flat/rising score component.
- Mechanical role-reversal and base heuristics can overfit noisy histories. Counts, dates, and thresholds must be exposed as evidence, while ambiguous cases remain `not_confirmed`.
- Monthly `resolution="M"` availability depends on the existing FireAnt client. Fetch failure must preserve a valid partial JSON object with an error and empty monthly metadata.
- The repository has unrelated staged and unstaged changes. This work must modify only the approved TA skill, its non-live CLI, focused tests, and dated reports.

## ACTIONS

1. Add a dedicated weekly structural-support reference covering MA compression, horizontal pivots, role reversal, base memory, volume, RSI reset, Wyckoff LPS/backup, weekly-close validation, scoring, and required output.
2. Extend the main skill contract and JSON schema to load and expose the weekly framework.
3. Add deterministic weekly indicators and evidence helpers to the CLI.
4. Add a focused test module using synthetic weekly OHLCV; no network calls.
5. Run baseline skill evaluations, focused unit tests, syntax checks, and final verification.

Next action: implement the approved plan without changing live trading logic.
