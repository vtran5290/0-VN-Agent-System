# OpSec Checklist — Anonymous Public Launch
**Date:** 2026-06-17
**Purpose:** Operational security protocol before and during public launch
**Council authority:** Opus judgment gate (2026-06-17) — writing-style hygiene elevated to #1 risk

> Anonymity is an operational constraint, not branding. The goal is not to be untraceable forever — it is to ensure that a determined but non-state-level actor (employer HR, a curious colleague, a journalist) cannot casually link the pen name to the real identity in Year 1.

---

## Priority Order (highest risk first, per Opus)

1. Writing-style fingerprint
2. Cross-platform metadata leakage
3. Domain / email / account separation
4. Device and network hygiene
5. Screenshot and file metadata
6. Employment contract skim
7. Incident response plan

---

## 1. Writing-Style Hygiene (highest risk)

**Why #1:** Stylometric matching is trivial. One person who reads both the operator's existing online presence and the new anonymous account can connect them in a single sitting, with no technical tools.

### Before writing any public content:

- [ ] **Inventory your existing online writing voice.** List:
  - Signature phrases you use often ("to be fair", "the key insight is", "worth noting")
  - Punctuation habits (em-dash heavy? Oxford comma? sentence fragments?)
  - Structural patterns (do you always open with a question? use bullet lists vs prose?)
  - Vocabulary quirks (Vietnamese-English code-switching patterns, industry jargon you prefer)
  - Emoji or formatting habits
  - Typical post length and rhythm

- [ ] **Build a personal "avoid" list** — 10–15 specific phrases/habits from your existing writing that must not appear on the anonymous account.

- [ ] **Establish a distinct anonymous voice** before writing anything public:
  - Choose: prose-heavy or bullet-heavy (different from your personal style)
  - Choose: formal/academic or terse/numerical (different from your default)
  - Stick to it consistently — inconsistency is its own fingerprint

- [ ] **Do not translate from Vietnamese internal notes directly** into English public posts. Translation carries style fingerprints.

- [ ] **Do not use the same framing** that appears in any LinkedIn article, GitHub README, or Substack you've written under your real name.

- [ ] **Case studies and examples:** Do not reference your personal investing history, employer experience, or career details — even obliquely ("when I worked in financial services...").

---

## 2. Account Separation

- [ ] **New email address** — never tied to real name, employer email, or personal recovery phone
  - Use ProtonMail or similar. Recovery: another new ProtonMail, not personal Gmail.
  - Do not add a real name to the account display name, even temporarily.

- [ ] **New social/publishing accounts** — created from the new email, not OAuth-linked to Google/Facebook/LinkedIn
  - X/Twitter: new account, new email, no profile image that has appeared elsewhere
  - Substack/Beehiiv: registered to new email only
  - GitHub (if open-sourcing anything): new account, no commits from personal GitHub repo transferred

- [ ] **No cross-linking** — the anonymous account never follows, references, or is followed by accounts linked to the real identity. One follow = a linkage trail.

- [ ] **No "also posted on" patterns** — do not cross-post from anonymous account to personal LinkedIn or vice versa.

- [ ] **Pen name selection:**
  - Do not use real initials
  - Do not use a name that is a translation or close derivative of the real name
  - Avoid names that appear in the operator's prior online handles

---

## 3. Domain and Infrastructure

- [ ] **Separate domain** for any landing page — registered with WHOIS privacy protection enabled from day 1 (Namecheap WhoisGuard, Cloudflare registrar, or equivalent)
  - Domain registered to new email, not personal email
  - Payment: ideally separate payment method (virtual card) or PayPal linked to new email

- [ ] **Static site hosting** preferred over dynamic:
  - Options: Netlify, Vercel, GitHub Pages (new account), Cloudflare Pages
  - No self-hosted VPS in Year 1 — infrastructure management is a distraction and a security surface
  - No Streamlit Cloud public deployment in Year 1 (Opus block)

- [ ] **Email collection (waitlist):** Use Substack or Beehiiv only — do not self-host
  - Both handle PDPD Decree 13/2023 compliance on the operator's behalf
  - Do not collect emails via a self-hosted form into a Google Sheet

- [ ] **No personal phone number** associated with any account — use virtual number (Google Voice or similar) if a phone is required for account verification

---

## 4. Device and Network Hygiene

- [ ] **Do not use work device** for any anonymous-account activity — ever
  - MDM agents on employer devices can log browser activity, keystrokes, and screen captures
  - This applies to: writing posts, checking the anonymous account, editing files for publication

- [ ] **Do not use work Wi-Fi** for anonymous-account activity — even personal device on work network
  - Corporate network traffic logs can link your personal device to specific URLs and accounts

- [ ] **Do not work on public content during employer work hours** if your contract has work-hours activity restrictions (check this in the contract skim — Gate 1)

- [ ] **Browser profile separation:**
  - Use a separate browser or browser profile exclusively for the anonymous account
  - Never log into personal Google/LinkedIn/Facebook in that profile
  - Consider: Firefox with uBlock Origin + no Google sync, or a dedicated Brave profile

- [ ] **VPN optional but not required** for Year 1 small free launch. Priority is account separation, not network-level anonymity.

---

## 5. Screenshot and File Metadata

- [ ] **Strip EXIF data** from any images before publishing — Windows: right-click → Properties → Details → Remove Properties. Or use ExifTool.

- [ ] **Check screenshots for:**
  - Windows username in file path (e.g., `C:\Users\YOURREALNAME\...` visible in Streamlit URL bar or terminal output)
  - Local file paths in HTML comments or report headers
  - Repo name in terminal output
  - API key fragments in error messages
  - Broker account numbers, order IDs, or NAV values
  - Taskbar icons revealing other open applications (LinkedIn, employer tools)
  - Clock showing work hours
  - Desktop wallpaper or folder names visible in window chrome

- [ ] **VS Code / editor screenshots:** Confirm no file explorer panel visible showing repo structure or real username in path

- [ ] **PDF metadata:** If publishing any PDF, strip author metadata with `exiftool -Author="" file.pdf`

- [ ] **HTML source:** Check generated HTML reports for hardcoded strings: file paths, username, `LOLII` (Windows username), API key references in comments, repo names

---

## 6. Employment Contract Skim (Gate 1)

Read the employment contract for these specific clauses **before** publishing anything. This is the primary gate — if any clause is ambiguous, get a brief legal read before proceeding.

- [ ] **Outside business activity / moonlighting clause:**
  - Does it require prior written approval for any outside work?
  - Does it restrict unpaid / non-commercial activity?
  - Does it apply even if the project is free and non-competing?

- [ ] **IP assignment clause:**
  - Does it assign to the employer any work created using employer resources (time, devices, data)?
  - Does it assign work created in your "field of work" regardless of when/where created?
  - If the employer is in financial services / technology, a broad IP clause could technically cover a financial analytics tool

- [ ] **Non-compete / non-solicitation:**
  - Does it restrict financial-services adjacent activities?
  - Does "financial services" appear in the restricted activities list?

- [ ] **Securities / trading conduct policy:**
  - Does the employer have a separate trading policy requiring disclosure of personal accounts?
  - Does that policy extend to model or paper trading?
  - Does it extend to publishing market analysis publicly?

- [ ] **Confidentiality:**
  - Does any confidentiality clause cover "insights developed in connection with your work"?
  - If any of the VN equity data, signals, or methods overlap with employer work product — flag immediately.

**Decision gate:**
- Clean contract (no financial-services restrictions, no broad IP assignment, no moonlighting approval required) → proceed with free launch
- Ambiguous clause → pause, get 30-minute employment lawyer read before launch
- Explicit restriction → stop, do not launch until resolved

---

## 7. Incident Response Plan

**If someone asks directly (online):** "Who are you? Where do you work?"
> Standard response: "I publish anonymously to keep the work independent. I'm not going to disclose personal details. Happy to discuss the methodology."
> Never confirm or deny employer, location, or identity. Do not get drawn into it.

**If a colleague or acquaintance recognizes the writing style:**
> Do not confirm or deny. Treat it as speculation. Do not make the mistake of over-denying ("that's definitely not me") which creates its own record.

**If the employer asks directly:**
> This is now a legal/HR matter, not an OpSec matter. Consult an employment lawyer before responding. Do not volunteer information.

**If a regulator or SSC inquiry arrives:**
> Stop all publishing immediately. Do not delete content (that can be obstruction). Consult a Vietnamese lawyer with securities-law experience. Do not respond to the inquiry without legal representation.

**Pre-incident hygiene (do this before launch):**
- [ ] Know the URL and account credentials for every anonymous account in a secure password manager
- [ ] Have a takedown plan: know how to unpublish Substack, delete domain, or remove static site within 30 minutes if needed
- [ ] Test the takedown plan once before launch — confirm you can remove all public content quickly
- [ ] Keep a private copy of everything published (in `data/private/`) — in case of dispute about what was said

---

## Summary Pre-Launch Checklist

- [ ] Writing-style "avoid" list built and reviewed
- [ ] New email created, not linked to real identity
- [ ] New social/publishing accounts on new email
- [ ] WHOIS privacy on domain
- [ ] No work device, no work Wi-Fi, no work hours
- [ ] Screenshot audit complete (no paths, usernames, keys, NAV visible)
- [ ] Employment contract skimmed — gate decision made (proceed / pause / stop)
- [ ] Disclaimer template added to all public content
- [ ] Takedown plan tested
- [ ] Incident response responses drafted (have them ready before first post)

---

*AI advisory only — not legal advice. Consult qualified Vietnamese legal counsel before any public launch.*
