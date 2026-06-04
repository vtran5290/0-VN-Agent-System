# Roadmap and Stage Tracker

## North Star

Build a safe, evidence-based Vietnam trading operating system that can progress from personal decision-support to private auto-execution, then to verified copytrade/content monetization, without sacrificing safety, reputation, or legal/compliance discipline.

## Long-term flywheel

```text
Clean workflow
→ order-intent dry run
→ tiny real sandbox
→ verified track record
→ public-safe content
→ broker/referral/copytrade monetization
→ improved process and trust
```

## Stage ladder

| Stage | Name | Status | Goal | Unlock condition | Hard stop |
|-------|------|--------|------|------------------|-----------|
| 0 | Manual decision-support | **CURRENT** | Weekly report + manual execution | 4 clean weekly cycles | stale data / no logs |
| 1 | Order-intent dry run | **NEXT** | System produces intended orders but sends none | 2–4 clean weeks | unsafe/confusing order |
| 2 | Tiny real sandbox | FUTURE | 20–50m VND EOD-only supported execution | explicit approval + dry-run evidence | unintended order / stale data |
| 3 | Scaled private account | FUTURE | larger private capital | 3+ months clean sandbox | drawdown/ops breach |
| 4 | Copytrade/public account | FUTURE | verified public track record | 6–12 months real record + compliance route | unclear legal/broker setup |
| 5 | Content/referral engine | FUTURE | education-led funnel | compliant content process | hype/pump/buy-call behavior |

**Current stage: Stage 0 — Manual decision-support.**  
**Next stage: Stage 1 — Order-intent dry run.**  
**Do not skip directly to live/copytrade/content automation.**

## Safety defaults (locked)

| Flag | Default |
|------|---------|
| `live_trading_enabled` | false |
| `copytrade_enabled` | false |
| `content_auto_posting_enabled` | false |
| `s3_production_enabled` | false |
| `intraday_order_routing_enabled` | false |

**Real capital: NO-GO** per `docs/trading/REAL_CAPITAL_READINESS.md`.

## Evidence counters (`data/roadmap/stage_tracker.yaml`)

| Counter | Meaning |
|---------|---------|
| `clean_weekly_cycles` | Full weekly pareto run + review, no stale-data override |
| `clean_order_intent_cycles` | Dry-run CSV generated; human reviewed; no confusion |
| `tiny_sandbox_live_days` | Stage 2 only — after explicit approval |
| `verified_real_track_record_months` | Stage 4+ |
| `manual_exceptions_logged` | Cloud vs CSV conflicts documented |
| `stale_data_incidents` | Scan/positions date mismatch incidents |
| `unintended_order_incidents` | Must stay 0 before any live stage |
| `outside_a3_holdings_reviewed` | Discretionary names logged in outside-A3 template |
| `order_intent_rows_reviewed` | Dry-run CSV human-reviewed |

**Last reviews** (`last_reviews` in YAML):

| Field | Meaning |
|-------|---------|
| `last_weekly_run_date` | Last `weekly_pareto_operator.ps1` run |
| `last_order_intent_date` | Last dry-run CSV generated/reviewed |
| `last_manual_review_date` | Last manual cloud exception / trade log entry |

## Commands

```powershell
python -m src.review.cli roadmap-status
```

### Evidence logging (after human review)

```powershell
python -m src.review.cli record-weekly-run --date YYYY-MM-DD `
  --weekly-reviewed `
  --order-intent-reviewed `
  --order-intent-rows-reviewed 12 `
  --outside-a3-reviewed 3 `
  --stale-data-incidents 0 `
  --unintended-order-incidents 0 `
  --notes "Reviewed weekly HTML + dry-run CSV"
```

- Appends one JSON line to `data/roadmap/weekly_review_log.jsonl` (append-only).
- Updates `data/roadmap/stage_tracker.yaml` summary (`as_of`, `last_reviews`, `evidence`).
- **`clean_weekly_cycles`** increments only with `--weekly-reviewed` and zero stale/unintended incidents this run.
- **`clean_order_intent_cycles`** increments only with `--order-intent-reviewed` and zero incidents this run.
- Running `weekly_pareto_operator.ps1` or generating files **does not** increment clean cycles — human review required.

**Do not hand-edit `clean_*` counters** unless recovering from a failed `record-weekly-run`. Use `roadmap-status` to verify.

Alt entrypoint: `python scripts/review/record_weekly_run.py` (same flags).

Monthly qualitative review: `templates/monthly_progress_review_template.md`.

## Current artifacts

| Artifact | Path |
|----------|------|
| Positions | `data/raw/current_positions_derived.json` |
| Scan | `data/research/portfolio_optimization/missing_work/phase36_daily_scan_latest.csv` |
| Weekly HTML | `reports/latest/index.html` |
| Order intent | `data/trading/order_intent/order_intent_YYYY-MM-DD.csv` |
| Manual log template | `templates/manual_decision_log_template.md` |

## Next action (default)

**Build and run order-intent dry run** — see `docs/trading/ORDER_INTENT_DRY_RUN.md`.
