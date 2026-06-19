# 7-Day Execution Plan — July 1 Free Launch
**Date:** 2026-06-17
**Target:** Free public launch by 2026-07-01 (14 days)
**Council authority:** Opus judgment gate (2026-06-17)

> The dominant workstream is sanitization (Opus verdict) — not landing page copywriting.
> The employment-contract skim is the gate that controls everything else.
> If the contract has ambiguous language, timeline shifts right by 7–14 days.

---

## Pre-Start Actions (today, before Day 1)

- [ ] **Decide pen name / project name** — needed before any public content is written. Pen name must not be: real initials, translation of real name, or similar to existing online handles.
- [ ] **Build the writing-style "avoid" list** — 10–15 phrases/habits from your existing online writing that must not appear on the anonymous account. Do this before drafting any copy.

---

## Day 1–2 (2026-06-18 to 2026-06-19): Employment Contract Gate

**This is the primary gate. Do not proceed to public content work until this is done.**

- [ ] Read the employment contract for the following clauses:
  - Outside business activity / moonlighting approval requirements
  - IP assignment scope (does it cover work in "your field"?)
  - Non-compete / financial-services restrictions
  - Securities / trading conduct policy
  - Confidentiality scope

- [ ] **Gate decision:**
  - **CLEAR:** No financial-services restrictions, no broad IP assignment, no moonlighting approval required for unpaid outside activity → proceed Day 3
  - **AMBIGUOUS:** Any clause that could plausibly apply → get a 30-minute employment lawyer read before proceeding. Push launch to Week 3.
  - **BLOCK:** Explicit restriction on financial-analysis / securities-adjacent outside work → stop, consult lawyer, reassess scope

- [ ] If CLEAR: note which specific clauses you checked and why each is not a blocker. Keep this note private — it is your Gate 1 rationale.

**Deliverable:** Gate 1 decision (proceed / pause / stop)

---

## Day 3 (2026-06-20): Account and Infrastructure Setup

*Only proceed if Gate 1 = CLEAR*

- [ ] **New email:** Create ProtonMail (or equivalent). Do not use personal recovery phone. Do not link to Google account.
- [ ] **Domain:** Register domain with WHOIS privacy enabled from day 1. Use new email for registration. Use virtual card or separate payment method if possible.
- [ ] **Substack or Beehiiv:** Register account on new email. Do not OAuth-link to personal Google/GitHub.
- [ ] **Social accounts (optional, if launching):** Create X account on new email. No profile image that appears elsewhere.
- [ ] **Password manager:** Add all new accounts. Do not store in browser profile tied to real identity.
- [ ] **Test takedown plan:** Confirm you can remove/unpublish all new accounts within 30 minutes if needed.

**Deliverable:** Anonymous infrastructure stack live and tested

---

## Day 4–6 (2026-06-21 to 2026-06-23): Artifact Sanitization

**Most underestimated workstream. Allocate full days.**

### Day 4: Pipeline split + private folder
- [ ] Create `data/private/` in the VN Agent repo
- [ ] Add to `.gitignore`:
  ```
  data/private/
  data/paper_trade/
  trade_logs/
  data/trading/
  ```
- [ ] Move to `data/private/`:
  - Paper-trade history files
  - Execution audit logs
  - NAV curve data
  - Allocation plan JSON
  - Any files with schema `{ticker: weight}` or `{ticker: action}`
- [ ] Confirm `git status` shows these folders as untracked / ignored

### Day 5: Report template sanitization
- [ ] Open the Cloud Daily Report HTML template
  - Search for: `signal`, `action`, `buy`, `sell`, `entry`, `exit`, `final_action`, `allocation`
  - Search for hardcoded strings: `LOLII`, `C:\Users\`, `D:\V\`, API key fragments
  - Search for HTML comments containing file paths or credentials
  - Replace or remove each instance per sanitization map (02_language_sanitization_map.md)
- [ ] Open the Weekly Report MD template
  - Same search-and-replace pass
  - Remove any `A3 action board` section
  - Remove any `if X, do Y` conditional language → replace with historical-observation framing
  - Confirm disclaimer appears at top and bottom

### Day 6: Dashboard and export audit
- [ ] Streamlit dashboard: confirm it will NOT be deployed publicly. Archive dashboard tab list — note which charts are safe for static-snapshot export.
- [ ] Export 2–3 safe static chart images for the first memo:
  - Regime state indicator (single label + date)
  - Breadth histogram (counts, no ticker names)
  - Sector RS heatmap (sector-level only)
- [ ] Strip EXIF from all exported images (Windows: right-click → Properties → Details → Remove Properties)
- [ ] Check each image for visible file paths, usernames, or NAV values in the frame

**Deliverable:** Sanitized pipeline. Private folder isolated. Safe images exported for first memo.

---

## Day 7–9 (2026-06-24 to 2026-06-26): Content Production

### Day 7: Landing page
- [ ] Substitute [NOTEBOOK_NAME] throughout `04_landing_page_copy.md`
- [ ] Run adversarial read: "Would employer HR or SSC investigator read any sentence as advice?" Fix any failures.
- [ ] Build as static site (Netlify / Cloudflare Pages / GitHub Pages on new account)
- [ ] Deploy to domain registered on Day 3
- [ ] Confirm HTTPS, WHOIS privacy active, no real name in page source or metadata

### Day 8: First weekly memo draft
- [ ] Fill in `05_weekly_memo_template.md` with actual data from the most recent framework run
- [ ] Run language sanitization pass — check every sentence against the replacement map
- [ ] Remove / redact: any ticker names with directional language, any NAV references, any allocation data
- [ ] Case study: select a historical period ≥6 months old (i.e., ≤ December 2025). Multi-stock, not single-name.
- [ ] Read aloud: does any sentence sound like advice? Fix it.
- [ ] Add disclaimer at top and bottom.

### Day 9: Launch post draft
- [ ] Fill in [NOTEBOOK_NAME] and [LANDING_PAGE_URL] in `06_launch_post.md`
- [ ] Select VERSION A (thread) or VERSION B (Substack post) based on platform choice
- [ ] Apply writing-style hygiene pass: check against your personal "avoid" list
- [ ] Do not post yet — hold for Day 13 final review

**Deliverable:** Landing page live. First memo draft complete. Launch post draft complete.

---

## Day 10–12 (2026-06-27 to 2026-06-29): Review Passes

### Day 10: Internal review
- [ ] Read everything as an adversary:
  - Employer HR reading the landing page: does anything suggest a securities-adjacent outside business?
  - SSC investigator reading the weekly memo: does anything read as unlicensed investment consulting?
  - A curious colleague who knows your writing: does any phrase match your normal voice?
- [ ] Fix every failure found

### Day 11: Screenshot and metadata audit
- [ ] Final check on all images to be published: no paths, usernames, keys, NAV visible
- [ ] Check landing page HTML source: no real name, no personal email, no identifiable metadata
- [ ] Check Substack/Beehiiv profile: anonymous name only, no real name, no personal social links

### Day 12: Dry run
- [ ] Send first memo draft to your own Substack/Beehiiv as a test send — confirm formatting
- [ ] View landing page from a private/incognito window as if seeing it for the first time
- [ ] Confirm waitlist form works and sends to anonymous email, not personal
- [ ] Confirm unsubscribe link works

---

## Day 13 (2026-06-30): Final Pre-Launch Checklist

- [ ] Employment contract Gate 1: CLEAR (confirmed Day 1–2)
- [ ] Private folder isolated from public pipeline: confirmed
- [ ] Paper-trade NAV and allocation JSON: confirmed NOT in any public output
- [ ] Streamlit dashboard: confirmed NOT deployed publicly
- [ ] All published artifacts: language-sanitized per map
- [ ] All images: EXIF stripped, no identifying metadata
- [ ] All accounts: on anonymous email, no personal cross-links
- [ ] Domain: WHOIS privacy active
- [ ] Disclaimer: top AND bottom of all published content
- [ ] Launch post: writing-style hygiene pass complete
- [ ] Incident response: know what you'll say if asked who you are
- [ ] Takedown plan: confirmed executable in <30 minutes

**Gate question:** Has anything surfaced in the past 13 days that changes the Gate 1 decision?
If yes → pause, assess, consult if needed.
If no → proceed.

---

## Day 14 (2026-07-01): Launch

**Order of operations:**
1. Publish landing page (should already be live from Day 7 — confirm live)
2. Publish first weekly memo on Substack/Beehiiv
3. Post launch thread (X) or announcement post
4. Do NOT announce on personal social accounts
5. Do NOT DM personal contacts about the launch

**Post-launch monitoring (first 48 hours):**
- [ ] Check for any unexpected traffic spikes or unusual engagement (could indicate the post was picked up by someone who knows you)
- [ ] Check for any DMs probing identity
- [ ] If anything unusual → pause new content, assess before next post

---

## What Is Explicitly NOT in This Plan

- LLC / entity registration
- Paid subscription setup
- Payment rails or Stripe integration
- B2B data sales
- CTCK partnership
- Copy-trading infrastructure
- Signal room or Telegram/Discord setup
- Pricing tests
- Valuation / commercial planning

All of the above wait until: (a) legal consult clears the product, (b) a track record of free memos exists, (c) entity/anonymity conflict is consciously resolved.

---

## Timeline Summary

| Day | Date | Activity | Gate |
|---|---|---|---|
| Pre-start | 2026-06-17 | Pen name + writing-style avoid list | — |
| 1–2 | 2026-06-18–19 | Employment contract skim | **Gate 1** |
| 3 | 2026-06-20 | Account + infrastructure setup | Requires Gate 1 CLEAR |
| 4–6 | 2026-06-21–23 | Artifact sanitization + pipeline split | — |
| 7–9 | 2026-06-24–26 | Content production (landing page, memo, post) | — |
| 10–12 | 2026-06-27–29 | Review passes + metadata audit | — |
| 13 | 2026-06-30 | Final pre-launch checklist | **Gate 2: all items must pass** |
| 14 | 2026-07-01 | Launch | — |

**If Gate 1 is ambiguous:** push entire timeline right by 7–14 days. Do not compress the legal read.

---

*AI advisory only — not legal advice. Consult qualified Vietnamese legal counsel before any public launch.*
