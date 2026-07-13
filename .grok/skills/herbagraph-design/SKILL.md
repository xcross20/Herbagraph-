---
name: herbagraph-design
description: >
  HerbaGraph brand and product design system for homepage, auth pages, and UI consistency.
  Use when designing or redesigning HerbaGraph marketing pages, login/signup flows, colors,
  typography, or aligning app/report surfaces with the clinical green brand. Triggers on
  "HerbaGraph design", "brand guide", "homepage design", "clinical UI", or site styling tasks.
  Load references/BRAND.md first; apply design-taste-frontend for landing pages only.
---

# HerbaGraph Design Skill

## When to use

- Public site: `index.html`, `login.html`, `signup.html`, `forgot-password.html`, `reset-password.html`
- Shared tokens: `frontend/css/site.css`
- Brand alignment across `app.html` and `report.html`
- Any request to make HerbaGraph "look correct" or match the product guide

## Workflow

1. Read `references/BRAND.md` for tokens, IA, copy, and design read.
2. For landing/auth work, also load user skill `design-taste-frontend` and declare the design read before coding.
3. Audit existing surfaces against brand tokens (especially: no Apple-blue `#0071e3` as primary).
4. Implement with **native CSS** in `frontend/css/site.css` (no build step in this repo).
5. Keep dashboard and report viewer changes to token harmonization unless explicitly scoped.

## Non-negotiables

- Primary accent: clinical green `#117744`, not purple or generic SaaS blue.
- Tagline: "AI Clinical Reasoning for Precision Nutrition" on public surfaces.
- Clinical disclaimer visible on homepage and auth footers.
- Trust-first density: no flashy motion, no three equal generic feature cards without visual variation.
- Product pages use the same header brand link to `/` and consistent Sign out → `/login.html` flow.

## File map

| File | Purpose |
|------|---------|
| `frontend/css/site.css` | Shared public + auth styles |
| `frontend/index.html` | Homepage |
| `frontend/report.html` | Canonical clinical report UI (token source) |
| `frontend/app.html` | Workspace shell |

## Pre-ship checklist (HerbaGraph public pages)

- [ ] Brand green on primary CTAs, WCAG AA contrast on buttons
- [ ] Tagline + disclaimer present
- [ ] No em-dashes in visible copy
- [ ] Homepage hero fits viewport (headline ≤ 2 lines, CTA visible)
- [ ] Auth pages link: forgot password, sign up, back to home
- [ ] Tokens match `references/BRAND.md`