# Paper Trading Operations Guide

**Status:** Paper-live observation only. **Real capital: NO-GO.** **DSE/DNSE live: NO-GO.** **`live_auto`: NO-GO.**

Execution ledger: `data/trading/live/` (per-account). **Do not use** `data/paper_trade/` (research/legacy).

## Paper accounts (capital)

| Account ID | Purpose | Starting NAV | Max order | Sizing |
|------------|---------|--------------|-----------|--------|
| `A3_DSE_PILOT_PAPER_SMALL` | Future DSE tiny pilot mimic | **30,000,000** VND | 5M | `cap_to_account_limits` (min trade 1M) |
| `A3_PROD_PAPER_5B` | A3 production reference | **5,000,000,000** VND | 500M | `scan_size_strict` |
| `A3_SCALE_PAPER_10B` | Medium-scale capacity check | **10,000,000,000** VND | 800M | `scan_size_strict` |
| `A3_SCALE_PAPER_20B` | Large NAV / liquidity stress | **20,000,000,000** VND | 1.2B | `cap_to_liquidity` |
| `S3_MAX60_SHADOW_PAPER` | S3 max60 shadow/radar | 0 (non-capital) | — | shadow only |

Config: `config/paper_accounts.yaml`

**Interpretation:** 30M = DSE pilot mimic; 5B = production reference; 10B = scale check; 20B = liquidity/capacity stress; S3 = radar only. Differences across accounts are **account sizing / liquidity capacity**, not strategy logic. 10B/20B are **not** new strategies — same A3_DP with different account constraints.

---

## Pareto cadence for solo operator

For a day-job operator, **do not run all five accounts every day** by default.

| Cadence | Accounts | Purpose |
|---------|----------|---------|
| **Weekly** | `A3_DSE_PILOT_PAPER_SMALL`, `A3_PROD_PAPER_5B` | OMS validation + production reference |
| **Monthly** | `A3_SCALE_PAPER_10B`, `A3_SCALE_PAPER_20B`, `S3_MAX60_SHADOW_PAPER` | Scale/capacity + S3 shadow checks |

- **Weekly paper cadence: A3_DSE_PILOT_PAPER_SMALL + A3_PROD_PAPER_5B**
- **Monthly only: A3_SCALE_PAPER_10B, A3_SCALE_PAPER_20B, S3_MAX60_SHADOW_PAPER**
- **S3** remains shadow/research only — not production P&L.
- **10B/20B** are scale/capacity checks, not weekly workload.
- Paper accounts validate future OMS readiness but are **not** the destination.
- Weekly **decision support** (report + order-intent dry run): `.\scripts\trading\weekly_pareto_operator.ps1` — see `docs/OPERATING_BACKBONE_PARETO.md`.

Accounts remain enabled in `config/paper_accounts.yaml`; cadence is operator discipline, not config disable.

---

## A. One-time setup

```powershell
cd "<repo_root>"
python -m src.trading.cli paper-accounts list
python -m src.trading.cli paper-accounts init --account A3_DSE_PILOT_PAPER_SMALL
python -m src.trading.cli paper-accounts init --account A3_PROD_PAPER_5B
python -m src.trading.cli paper-accounts init --account A3_SCALE_PAPER_10B
python -m src.trading.cli paper-accounts init --account A3_SCALE_PAPER_20B
python -m src.trading.cli paper-accounts init --account S3_MAX60_SHADOW_PAPER
```

---

## B. Daily pre-check

Production scan alias (written by `--step scan`):

`data/research/portfolio_optimization/missing_work/phase36_daily_scan_latest.csv`

Legacy name `phase36_daily_scan_sample.csv` is the same EOD output; resolver requires `--allow-sample` if you point at that path directly.

```powershell
python -m src.trading.cli resolve-scan --date YYYY-MM-DD --scan-path data/research/portfolio_optimization/missing_work/phase36_daily_scan_latest.csv
```

**Scheduled policy (Mon-Fri 16:30):** calendar date must match scan `as_of_date`. If stale (e.g. Monday with Friday scan only), the run **stops** and writes `paper_live_report_YYYYMMDD.md` — it does not silently trade stale data.

**Manual backfill only** (explicit operator override — not for scheduled runs):

```powershell
.\scripts\trading\daily_paper_live_full_run.ps1 -Date YYYY-MM-DD -UseLatestScanDate -Force
```

- `-UseLatestScanDate` — outputs use scan `as_of_date` (e.g. Friday data on Monday), not calendar date.
- `-Force` — bypasses existing run lock **only** after confirming the prior run was incomplete and no partial fills must be preserved.
- Do **not** add these flags to the 16:30 scheduled task.
- Do **not** silently run Friday scan as Monday without this explicit override.

Validate old duplicate task is disabled:

```powershell
.\scripts\trading\register_daily_paper_live_task.ps1 -DisableOld1600
schtasks /Query /TN "VN_Agent_Daily_Paper_Live_1600" /V /FO LIST
```

---

## C. Scheduled daily run (16:30)

Task: `VN_Agent_Daily_Paper_Live_1630` (register via `.\scripts\trading\register_daily_paper_live_task.ps1 -DisableOld1600`)

```powershell
.\scripts\trading\daily_paper_live_full_run.ps1
```

Troubleshooting if Task Last Result != 0:

- `data/trading/live/accounts/logs/paper_live_full_YYYYMMDD_*.log`
- `data/trading/live/accounts/paper_live_report_YYYYMMDD.md`
- If **no log**: check task WorkingDirectory = repo root, script path, user logged on
- Disable duplicate: `schtasks /Change /TN VN_Agent_Daily_Paper_Live_1600 /DISABLE`

---

## D. Daily paper-live run (main command)

```powershell
python -m src.trading.cli paper-accounts run-all --date YYYY-MM-DD --scan-path <phase36_csv> --include-s3-shadow
```

Or full script (scan + resolve + run-all + report):

```powershell
.\scripts\trading\daily_paper_live_full_run.ps1 -Date YYYY-MM-DD
```

**What it does:**
1. Resolves scan once
2. Runs `A3_DSE_PILOT_PAPER_SMALL` → `A3_PROD_PAPER_5B` → `A3_SCALE_PAPER_10B` → `A3_SCALE_PAPER_20B`
3. Optionally updates S3 shadow ledger (`--include-s3-shadow` only; S3 never uses A3 live-workflow)
4. Writes per-account dashboards + compare report (all 4 A3 accounts) + operator summary

Flags: `--force`, `--allow-sample`, `--test-mode`, `--continue-on-error`

Outputs:
- `data/trading/live/accounts/run_all_summary_YYYYMMDD.md`
- `data/trading/live/accounts/compare_YYYYMMDD.md`
- `data/trading/live/accounts/daily_operator_pack_YYYYMMDD.md` — **paste this into ChatGPT**
- `data/trading/live/accounts/valid_paper_day_YYYYMMDD.json` — validity gate (check if invalid/warnings)
- Per-account `dashboard/latest_status.json` (traffic light)

**20B cash drag interpretation** (not strategy degradation):
1. 5B scan-size basis (targets sized for 5B reference NAV)
2. ADV/liquidity caps
3. Max order cap
4. Insufficient signals / under-deployment
5. True capacity limit

Use capacity attribution in compare report + operator pack before concluding strategy weakness.

---

## D. Manual review (per account)

```powershell
python -m src.trading.cli manual-review --date YYYY-MM-DD --account A3_PROD_PAPER_5B
python -m src.trading.cli manual-review --date YYYY-MM-DD --account A3_DSE_PILOT_PAPER_SMALL
```

Edit: `data/trading/live/accounts/<ACCOUNT_ID>/manual_review_queue_YYYYMMDD.csv`

- Set `approved=true` only after reviewing scan row
- If `approval_stale=true`, re-review required (row content changed)
- Approval in account A does **not** affect account B

Apply:

```powershell
python -m src.trading.cli apply-manual-review --date YYYY-MM-DD --account A3_PROD_PAPER_5B
python -m src.trading.cli apply-manual-review --date YYYY-MM-DD --account A3_DSE_PILOT_PAPER_SMALL
```

Re-run workflow for that account if needed after approval (or use approved intents on next run).

---

## E. Summaries

```powershell
python -m src.trading.cli paper-accounts summary --account A3_PROD_PAPER_5B
python -m src.trading.cli paper-accounts summary --account A3_DSE_PILOT_PAPER_SMALL
python -m src.trading.cli s3-shadow summary
python -m src.trading.cli paper-accounts compare --date YYYY-MM-DD
```

---

## F. Traffic light (per account dashboard)

| Status | Meaning |
|--------|---------|
| **GREEN** | Workflow OK, recon clean, kill switch clear |
| **YELLOW** | Manual review pending, sizing constraints, no fills |
| **RED** | Data health critical, dirty recon, stale/sample scan |

See: `accounts/<ACCOUNT_ID>/dashboard/latest_status.json`

---

## G. Safety checklist

- [ ] No DSE/DNSE live API calls
- [ ] No `live_auto`
- [ ] No writes under `data/paper_trade/`
- [ ] S3 shadow separate from A3 P&L
- [ ] Manual approval does not bypass risk engine
- [ ] Non-DSE real manual account **not** connected to this system

---

## H. Paper-live hygiene (post-review, 2026-05-18)

**Observation policy**

- Paper-live may continue **only when** `phase36_daily_scan_latest.csv` has `as_of_date` matching the calendar run date (fresh EOD panel).
- If scan is **stale**, the daily script **STOPs by design** (exit **2**), writes `paper_live_report_YYYYMMDD.md` and a bootstrap log — do not treat as a bug.
- Do **not** use `-UseLatestScanDate` on the scheduled task; backfill only with explicit operator intent and `-Force` when run-lock allows.

**Scheduled tasks**

| Task | Expected state |
|------|----------------|
| `VN_Agent_Daily_Paper_Live_1630` | **Enabled** — production Mon–Fri 16:30 |
| `VN_Agent_Daily_Paper_Live_1600` | **Disabled** or not found — duplicate; must not run |

Verify:

```powershell
schtasks /Query /TN "VN_Agent_Daily_Paper_Live_1600" /V /FO LIST
schtasks /Query /TN "VN_Agent_Daily_Paper_Live_1630" /V /FO LIST
```

Disable old task if needed:

```powershell
.\scripts\trading\register_daily_paper_live_task.ps1 -DisableOld1600
```

**Capital / routing (unchanged)**

- Real capital: **NO-GO**
- DSE/DNSE live: **NO-GO**
- `live_auto`: **NO-GO**
- Intraday preview CSV: **not** routed to production OMS
- S3 / PTS: shadow/research only — no promotion

**Test evidence:** `review_outputs/post_third_ai_patch_test_output.txt`, `review_outputs/pytest_trading_all_20260518.txt`

---

## Individual account run (optional)

```powershell
python -m src.trading.cli live-workflow --mode paper --date YYYY-MM-DD --scan-path <csv> --account A3_PROD_PAPER_5B
python -m src.trading.cli live-workflow --mode paper --date YYYY-MM-DD --scan-path <csv> --account A3_DSE_PILOT_PAPER_SMALL
python -m src.trading.cli s3-shadow update --date YYYY-MM-DD --scan-path <csv>
```

`S3_MAX60_SHADOW_PAPER` cannot use `live-workflow` — use `s3-shadow update` only.
