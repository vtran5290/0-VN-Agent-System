# Outside-A3 Holding Review

> Holdings with label `DISCRETIONARY_OUTSIDE_A3` (or similar) are **manual/discretionary**.  
> They **do not** drive A3 production signals or OMS order-intent actions.

## Classification labels

| Label | Meaning |
|-------|---------|
| `A3_PRODUCTION_MATCHED` | Has `A3_PRODUCTION` row in phase36 scan; `final_action` applies |
| `DISCRETIONARY_OUTSIDE_A3` | Held manually; no production scan match |
| `LEGACY_POSITION` | Pre-system or pre-A3 book; review for exit or migration |
| `WATCHLIST_ONLY` | On radar; not a production position |
| `RESEARCH_SHADOW` | S3/research lane only; never production capital |

---

## Holding review (one row per ticker)

Ticker:
Label: DISCRETIONARY_OUTSIDE_A3 / LEGACY_POSITION / WATCHLIST_ONLY / RESEARCH_SHADOW
Reason held:
Entry thesis:
Exit rule:
Invalidation level:
Review date:
Will be added to A3 universe? Yes / No / Unknown

---

## Weekly operator note

- Order-intent dry run sets `holding_classification=DISCRETIONARY_OUTSIDE_A3` when no `A3_PRODUCTION` match.
- No OMS action is created for these rows (`suggested_action=NO_ACTION_FAIL_CLOSED`).
- Log manual cloud exceptions separately: `templates/manual_decision_log_template.md`
