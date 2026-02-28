# Trade Review Layer (TRADE_POSTMORTEM_LAYER)

**Purpose:** Study past executed trades to optimize execution: *what could have been done better*, using trade history + market/stock context + masters “brains” (Buffett, O’Neil, Minervini, Morales). No change to existing risk/regime/allocation/signal logic.

## Cadence

- **Monthly:** Run after month close; produces lesson learned for that month.
- **Ad-hoc:** Use `--start YYYY-MM-DD --end YYYY-MM-DD` for a custom window.

## How to run

### CLI (recommended)

From repo root:

```bash
# Build canonical input (parses md + optional closed trades JSON)
python -m src.review.cli build-input --month YYYY-MM

# Run diagnostics (patterns, trade_cards, what_could_be_better)
python -m src.review.cli diagnose --month YYYY-MM

# Masters review (Buffett/O'Neil/Minervini/Morales, LEAN, no transcript)
python -m src.review.cli masters --month YYYY-MM

# Write lesson template + insight bursts
python -m src.review.cli write-lessons --month YYYY-MM

# Run all steps in one go
python -m src.review.cli run-monthly --month YYYY-MM
```

**Default month:** If `--month` is omitted, the CLI uses the latest completed month from `data/raw/manual_inputs.json` (asof_date) or current month.

**Ad-hoc window:**

```bash
python -m src.review.cli build-input --start 2026-01-01 --end 2026-01-31
python -m src.review.cli diagnose --month 2026-01
python -m src.review.cli masters --month 2026-01
python -m src.review.cli write-lessons --month 2026-01
```

### Makefile (optional)

```bash
make trade-review-monthly
```

Override month:

```bash
make trade-review-monthly MONTH=2026-01
```

## Inputs

- **data/raw/trade_history_open_positions.md** — K–M rule; open positions (symbol + lots).
- **data/raw/current_positions_digest.md** — Current positions digest.
- **data/raw/trade_history_closed.json** — Optional; list of closed trades. **Bắt buộc tối thiểu:** `ticker`, `entry_date`, `exit_date`. Nên có thêm `entry_price`, `exit_price`, `lots`, `stop_price_at_entry`, `stop_source`, `reason_tag`, `exit_tag` để diagnostics mạnh (R-multiple, giveback, compliance).
- **data/raw/manual_inputs.json** — Latest macro/market snapshot for context.
- **data/raw/tech_status.json** — Optional; per-ticker tech (close_below_ma20, day2_trigger, tier).
- **data/decision/review_policy.json** — Thresholds and triggers for insight bursts; created with defaults if missing.

## Outputs (all under data/decision/)

| File | Description |
|------|-------------|
| trade_review_input.json | Canonical input for the review window (input_hash, trades_closed, positions_open). |
| trade_diagnostic_YYYY-MM.json | Summary stats, patterns (entry/exit/sizing/process), trade_cards with what_could_be_better. |
| trade_masters_review_YYYY-MM.json | Per-trade, per-master short review (mistake_type, 1_rule_adjust, confidence). |
| lesson_learned_YYYY-MM.md | Template: performance summary, top patterns, rule adjustments, what not to change, open questions. |
| lesson_learned_latest.md | Copy of latest lesson (overwritten each run). |
| open_positions_hygiene.json | Portfolio hygiene (r_multiple_missing_rate, stop_missing_rate, tier_coverage, sector_concentration) + regime_compliance. Hữu ích khi n_closed=0. |
| review_policy.json | min_sample_to_act (≥10 mới đề xuất rule change), cooldown (max_rule_changes_per_month: 1), `default_stop` (enabled + default_stop_pct), `process_gate` (stop_present_min, stop_manual_min, reason_tag_present_min), compliance_thresholds (RED/YELLOW/GREEN), triggers, rule_change_proposals (never auto-applied). |

## How proposals get reviewed

- **rule_change_proposals** in `review_policy.json` are **not** auto-applied. They are suggestions only.
- **Guardrails:** `min_sample_to_act` (n_closed ≥ 10 mới đề xuất rule change); `cooldown.max_rule_changes_per_month: 1` (tránh đổi liên tục); `process_gate` (stop_present_min, reason_tag_present_min) — khi gate ON chỉ cho phép **process fixes** (stop + tag), chặn mọi strategy tweaks.
- Review `lesson_learned_YYYY-MM.md` and `trade_diagnostic_YYYY-MM.json` manually; decide whether to change engine rules in code/config.
- Masters output is LEAN (no transcript); use it as input to human judgment, not as automatic rule updates.

## Idempotency and auditability

- Same inputs → same outputs. Rerun for the same period produces the same JSON/md unless source files change.
- `input_hash` in trade_review_input and diagnostic allows verifying that a run used a given input set.
- Logging: one-line summary at INFO; details at DEBUG.
