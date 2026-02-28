# Open Risk Dashboard — Position risk × Regime × Concentration

**Purpose:** Provide a structure-only (no PnL) view of open positions: coverage/quality, exposure concentration, holding age, regime overlay, and actionable flags. Does not change trading logic; data hygiene and provenance only.

## Outputs

- `data/decision/open_risk_YYYY-MM.json`
- `data/decision/open_risk_latest.json`
- `data/decision/open_risk_*.md` (when `--render`)

## Inputs

- `data/raw/current_positions_derived.json` — source of truth for open positions (from `derive-current`).
- `data/raw/manual_inputs.json` — asof_date, market context.
- `data/decision/regime_state.json` — regime, risk_flag, dist_days if available.
- `data/decision/review_policy.json` — `open_risk` thresholds (very_old_days, concentration_top1_share_red, concentration_hhi_red).

## Ticker sanitize (derive-current)

Before positions reach the dashboard, `derive-current` filters out non-stock labels so garbage from Excel does not affect open_risk or downstream analytics.

### Blacklist (skip_blacklisted_token)

Rows whose parsed ticker (after strip, upper, A–Z0–9 only) matches any of these tokens are skipped (case-insensitive):

- **Exchanges / boards:** `HNX`, `HOSE`, `UPCOM`, `HOS`
- **Indices:** `VNI`, `VNINDEX`, `VN30`
- **Labels:** `MAXBUY`, `HOLIDAYS`, `SUMMARY`, `TOTAL`, `ALL`, `TONG`

Counts and examples are in `data/raw/current_positions_skip_report.json` under `skip_blacklisted_token`.

### Numeric-only (skip_numeric_only)

VN tickers are not numeric-only. If the parsed ticker is **all digits** (e.g. `18450` from a misplaced Quantity or row label), the row is skipped with reason `skip_numeric_only`. This avoids Excel artifacts being treated as tickers.

### Other rules

- Ticker length &lt; 2 → `skip_invalid_ticker_format`.
- Final validation: regex `^[A-Z0-9]{2,8}$` (blacklist and numeric-only checks run before this).

## Concentration metrics and low coverage

Concentration stats (top10_by_lots, herfindahl_lots, single_name_lots_share_max) are computed **only from positions with valid lots** (`lots != null` and `lots > 0`).

- If **fewer than 3 positions** have valid lots:
  - `exposure_concentration.herfindahl_lots` and `exposure_concentration.single_name_lots_share_max` are set to **null**.
  - `coverage_quality.concentration_low_coverage` is **true**.
  - A top action is added: *"Concentration stats unavailable (fewer than 3 positions with lots); fill lots for coverage."*

This avoids fake concentration from missing lots; the dashboard still writes and other sections (e.g. regime_overlay, position_risk_cards) remain valid.

## Validation

- `validate_open_risk(payload)` (in `src/quality/validators.py`) checks required keys and `n_positions == len(position_risk_cards)`. Concentration metrics may be null.
- CLI `open-risk` runs this validator after writing and logs warnings on failure (does not fail the pipeline).

## CLI

```bash
python -m src.review.cli open-risk [--month YYYY-MM] [--render]
```

`run-monthly` calls open-risk after meta-perf (without `--render`).
