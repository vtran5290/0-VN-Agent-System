# Quan Trắc — Landing Page Deployment Guide
**Date:** 2026-06-19

---

## Option A: Cloudflare Pages (Recommended — free, fast, anonymous-friendly)

### Step 1: Create anonymous Cloudflare account
- Use your ProtonMail (the same one as Substack/X)
- Do NOT link to personal Cloudflare account

### Step 2: Deploy
```bash
# From a clean browser / device (not work machine)
# Option 1: Direct upload (no GitHub needed)
1. Log into dash.cloudflare.com
2. Go to Workers & Pages → Create → Pages → Upload assets
3. Upload the landing_page.html file (rename to index.html first)
4. Cloudflare assigns a *.pages.dev URL automatically

# Option 2: If you want a custom domain
1. Register domain at Namecheap/Porkbun with WHOIS privacy ON
2. In Cloudflare Pages → Custom domains → Add your domain
3. Cloudflare handles SSL automatically
```

### Step 3: Verify
- [ ] Page loads over HTTPS
- [ ] WHOIS privacy is active (check: whois.domaintools.com)
- [ ] No real name in page source (View Source → Ctrl+F your name)
- [ ] Waitlist form submits (once Substack embed URL is filled)
- [ ] Mobile responsive (check on phone)

---

## Option B: Netlify (Alternative — also free)

```bash
# Direct deploy (no GitHub)
1. Go to app.netlify.com → sign up with ProtonMail
2. Drag-and-drop: create a folder with index.html (renamed from landing_page.html)
3. Netlify assigns a *.netlify.app URL
4. Custom domain: Netlify → Domain settings → Add custom domain
```

Optional netlify.toml (place next to index.html):
```toml
[build]
  publish = "."

[[headers]]
  for = "/*"
  [headers.values]
    X-Frame-Options = "DENY"
    X-Content-Type-Options = "nosniff"
    Referrer-Policy = "strict-origin-when-cross-origin"
```

---

## Option C: GitHub Pages (NOT recommended)

GitHub Pages would require a public repo or a separate anonymous GitHub account. Since the main repo exposure is already a concern, avoid linking deployment to any GitHub account tied to your identity.

---

## Before Deploying: File Prep

```bash
# 1. Rename file
copy landing_page.html index.html

# 2. Fill the Substack embed URL (after creating Substack account)
# In index.html, replace both instances of:
#   [SUBSTACK_OR_BEEHIIV_EMBED_URL]
# with your actual Substack subscribe form URL, e.g.:
#   https://quantrac.substack.com/subscribe

# 3. Fill the landing page URL in other files
# In memo_001, launch_post, and issue_000:
# Replace [LANDING_PAGE_URL] with your actual URL
```

---

## Domain Recommendations

| Option | Domain | Cost | Notes |
|---|---|---|---|
| Free (Cloudflare) | quantrac.pages.dev | Free | Works, but less memorable |
| Free (Netlify) | quantrac.netlify.app | Free | Same |
| Custom | quantrac.vn | ~$25/yr | Best brand fit but .vn requires local registration |
| Custom | quantrac.co | ~$10/yr | Clean, international |
| Custom | quantracmarket.com | ~$10/yr | Available (check) |
| Substack native | quantrac.substack.com | Free | No separate hosting needed |

**Simplest path:** Skip custom domain for launch. Use quantrac.substack.com as the primary URL and rely on Substack's built-in landing page. Custom domain can come later.

---

## Post-Deploy Checklist

- [ ] Landing page loads at final URL
- [ ] Both waitlist forms submit to Substack
- [ ] PDPD privacy notice visible below forms
- [ ] Disclaimer visible in footer area
- [ ] No real name, email, or path in HTML source
- [ ] WHOIS privacy active (if custom domain)
- [ ] SSL/HTTPS working
- [ ] Mobile view tested
- [ ] EXIF stripped from any images on page
- [ ] Substack profile links back to landing page
- [ ] X bio links to landing page
- [ ] Facebook page links to landing page

---

## Simplest Launch Path (If Short on Time)

Skip the custom landing page entirely for July 1. Instead:

1. Create Substack at quantrac.substack.com
2. Use Substack's built-in landing page (they provide one)
3. Customize: add the "About" text from issue_000_about.md
4. Publish Issue 000 on June 28, Issue 001 on July 1
5. Link X/Facebook/TikTok bios to quantrac.substack.com
6. Deploy the custom landing_page.html later when you have time

This removes the deployment step entirely and lets you launch with zero hosting.

*Not investment advice. Deployment guide only.*
