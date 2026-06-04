# Report UX Style Guide — VN Agent System Stage 0

_Last updated: 2026-05-26_

This guide defines the visual and structural conventions for all Stage 0 operator reports.
It applies to: Cloud Daily Report HTML, Daily Scan Markdown, Weekly Report HTML, and standalone lens cards.

---

## 1. Decision Hierarchy (what every report must answer)

Every report surfaces these questions in order:

1. **What changed?** — Delta vs previous report (Section H in Cloud Daily).
2. **So what?** — Regime, breadth zone, T1/T2 permission status (Section B summary cards).
3. **What needs review?** — Actionable rows only: NEW_T1, EXIT_REVIEW (Section C, Section B).
4. **What is context only?** — Distribution Risk, RS Correction, Research Intake (Section G).
5. **What is the source of truth?** — Explicit SSOT label on every action section.

---

## 2. Section Labels

Use the following labels consistently to separate action from context:

| Label | CSS class | Color | When to use |
| --- | --- | --- | --- |
| `ACTION SSOT: final_action` | `.ssot-tag` | Green border | Sections B, C — anything tied to `final_action` |
| `MARKET CONTEXT` | `.ctx-tag` | Blue/muted border | Section G, Distribution Risk card, RS Correction card |
| `RESEARCH CONTEXT` | `.ctx-tag` | Blue/muted border | Research Intake, Institutional Accumulation output |
| `DATA QUALITY` | `.warn-banner` | Red border | Stale data, missing files, scan file warnings |
| `APPENDIX` | plain section-title | Neutral | Section I — full scan table, files used |

**Rule:** Never place a context-lens label (MARKET CONTEXT) alongside an action section. Never place an ACTION SSOT label on Distribution Risk, RS Correction, or Research Intake sections.

---

## 3. Color Logic

| Color | Hex (dark theme) | Use |
| --- | --- | --- |
| Green | `#5edd5e` / bg `#1a3a1a` | Bull regime, constructive action, T1 OK |
| Amber/Orange | `#ffc107` / bg `#3a2800` | Manual review required, caution, preview mode |
| Red | `#f77` / bg `#3a1010` | Exit signals, stale data, T2 blocked, bear regime |
| Blue/Gray | `#8ab4f8` / bg `#1e2a38` | Context, neutral metadata, section titles |
| Muted blue | `#6a9cc8` / bg `#0f1e2e` | MARKET CONTEXT labels, ctx-safety boxes |
| Muted green | `#5edd5e` / bg `#0f2010` | ACTION SSOT labels |

**Rule:** Do not use green to highlight context lenses. Do not use red for neutral data.

---

## 4. Badge Definitions

Badges are inline `<span class="badge bg-{color}">` elements. Use sparingly.

| Badge text | Color class | When |
| --- | --- | --- |
| `MODE: EOD` | `bg-green` | EOD report mode |
| `MODE: PRE-LUNCH PREVIEW` | `bg-amber` | Intraday mode |
| `VNINDEX: BULL` | `bg-green` | regime_bull = True |
| `VNINDEX: BEAR` | `bg-red` | regime_bull = False |
| `BREADTH: NORMAL` | `bg-green` | breadth_zone = normal |
| `BREADTH: CAUTION` | `bg-amber` | breadth_zone = caution |
| `BREADTH: DEFENSE` | `bg-red` | breadth_zone = defense |
| `T1: OK` | `bg-green` | breadth_t1_permission = True |
| `T1: BLOCKED` | `bg-red` | breadth_t1_permission = False |
| `T2: OK` | `bg-green` | breadth_t2_permission = True |
| `T2: BLOCKED` | `bg-red` | breadth_t2_permission = False |

---

## 5. RS Correction Bucket Labels

RS bucket names map to display labels in HTML:

| Raw bucket | Display label | Color |
| --- | --- | --- |
| `leader_strong` | LEADER | green |
| `outperform` | OUTPERFORM | green |
| `relative_flat` | FLAT | gray |
| `underperform` | UNDERPERFORM | red |
| `laggard` | LAGGARD | red |

---

## 6. Warning Banner Style

```html
<div class="warn-banner">⚠ Warnings: <ul>...</ul></div>
```

- Red background `#3a0f0f`, red border `#c0392b`.
- Use only for: stale data, missing scan file, `auto_order_allowed=True` safety violation, `NEEDS_REVIEW` status.
- Do not use for informational notes. Use `.footnote` instead.

---

## 7. Context Safety Box Style

```html
<div class="ctx-safety">Text here.</div>
```

- Muted blue-left-border box.
- Use at the top of every context-lens section (Section G, Distribution Risk card, RS Correction card).
- Required text: "X is [market/leader/research] context only. It does **not** set or override `final_action`."

---

## 8. Section Order (Cloud Daily Report)

| Section | ID anchor | Label type | Content |
| --- | --- | --- | --- |
| Header strip | — | — | Regime badges, NAV, mode, timestamp |
| Nav bar | — | — | Jump links to B–I |
| Warnings banner | — | DATA QUALITY | Stale, missing, safety violations |
| B. Decision Summary | `#section-b` | ACTION SSOT | ACTION NOW / WATCH / DO NOT DO cards |
| C. A3 Action Board | `#section-c` | ACTION SSOT | T1, T2, Exit, Hold tables |
| D. Portfolio Overlay | `#section-d` | — | Holdings × scan join |
| E. Intraday Preview | `#section-e` | — | Intraday mode only |
| F. S3 Radar | — | — | Paper-shadow only disclaimer |
| G. Market / Breadth / Risk | `#section-g` | MARKET CONTEXT | Breadth KV table + DRL card + RS card |
| H. Delta vs Previous | `#section-h` | — | Changes from last report |
| I. Appendix | `#section-i` | — | Full scan table (collapsible), files used |

---

## 9. Table Style

- `border-collapse: collapse`, full width, font-size `0.82rem`.
- Sticky `<th>` headers (`position: sticky; top: 0`).
- Row color coding via left-border: green = constructive, amber = review, red = exit/risk, gray = neutral.
- Wide tables wrapped in `.scroll-table` div for horizontal scroll.
- Avoid more than 12 columns in any visible (non-appendix) table.

---

## 10. SSOT Safety Rules (non-negotiable)

These rules must be preserved in every report render:

1. `final_action` is the only production action field. No other field overrides it.
2. Distribution Risk Lens is market context only. Required note on every DRL card.
3. RS Correction Lens is market/leader context only. Required note on every RS card.
4. Research Intake / Institutional Accumulation is research/ranking context only.
5. Order-intent sends no orders. No OMS routing.
6. No live trading. Real capital: NO-GO.
7. S3 shadow is paper only. Required disclaimer on every S3 section.

---

_This guide applies to all Stage 0 reports. Do not apply these styles to OMS, DNSE, or live-capital systems._
