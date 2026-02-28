# Token Optimization — Lean Mode vs Debug Mode

## Council

**Lean Mode (default)**  
- Each brain outputs a **vote card** only: `stance`, `confidence`, `top_3_evidence` (≤10 words each), `top_2_risks`, `change_my_mind`.  
- No narrative paragraphs. No transcript-style debate.  
- Orchestrator aggregates: vote distribution, weighted confidence, key disagreements (max 3).  
- **conflict_trigger:** If material vote dispersion OR `risk_flag=High` OR blockers → enable **deep_debate** (max 5 sentences per brain, disagreement only).  
- Output: `council_output_json` with `votes`, `vote_distribution`, `key_disagreements`, `conflict_trigger`, `deep_debate_used`.

**Debug Mode (`--council-debug`)**  
- Full transcript: Data Quality, per-brain narrative (Likes/Dislikes/Risk/Action/Invalidation), Council Agreements/Conflicts, Guardrail Risk Flags.  
- Use only when auditing or debugging.

## Weekly Report

**Data Mode (default)**  
- `python -m src.report.weekly` → writes **weekly_report.json** only (structured payload: `asof_date`, `data_confidence`, `what_changed`, `triggers_fired`, `actions`, `risks`, `open_questions`).  
- No markdown. No prose.

**Render Mode (`--render`)**  
- `python -m src.report.weekly --render` → writes **weekly_report.json** and **weekly_report.md** (readable report).  
- `make weekly` uses `--render` so the human-readable report is produced.

## Logging

- **INFO:** One-line summary (e.g. `Weekly: weekly_report.json | regime_state.json | archive=...`).  
- **DEBUG:** Verbose FireAnt/VNI, distribution days, HNX/UPCOM. Set `logging.level=DEBUG` when needed.  
- Non-critical VNI warnings (e.g. `latest_close=None`) are DEBUG only; no console spam when vnstock/ingestion already provided levels.

## Decision Storage

- **decision_log/<date>.json:** Full audit log; includes `input_hash` (hash of manual_inputs + tech_status + watchlist_scores) for auditability.  
- **data/decision/decision_digest.csv:** One row per run: `date`, `regime`, `risk_flag`, `gross_cap`, `new_buys_allowed`.  
- Council **vote cards** kept in `council_output.json`; full debate transcript not stored by default.

## Backtest Section

- If knowledge records exist: one line per ticker with **win_rate**, **expectancy**, **sample_size (n)**, **regime_filter** only.  
- If none: `No backtest records available.`  
- Full ledger not loaded or printed.

## Rules (no change to logic)

- Do not change: risk engine, allocation rules, regime engine, signal generation, council voting math, secretary checklist logic.  
- Only representation and verbosity are optimized.  
- STRICT JSON in data mode; no markdown, no long prose, no duplication of static values.
