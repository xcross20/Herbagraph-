# HerbaGraph Brand & Product Design Reference

Source of truth: `frontend/report.html` (clinical report UI), `herbagraph7.pdf` (product export), README Design Philosophy.

## Positioning

- **Product:** Explainable biological reasoning platform for lab biomarker intelligence.
- **Tagline:** AI Clinical Reasoning for Precision Nutrition.
- **Audience:** Licensed practitioners, researchers, clinical decision-support workflows. Not consumer wellness hype.
- **Tone:** Calm, evidence-forward, transparent about uncertainty. Assist human judgment; never replace it.
- **Mandatory disclaimer:** Research / educational tool. Not medical advice. Every CTA and footer reinforces clinician discussion framing.

## Design philosophy (product)

1. Explain every conclusion.
2. Quantify uncertainty rather than hide it.
3. Separate evidence from opinion.
4. Assist human decision-making rather than replace it.

## Visual identity (extracted from report viewer)

### Color tokens

| Token | Value | Use |
|-------|-------|-----|
| `--hg-brand` | `#117744` | Primary clinical green (report uses `#174`) |
| `--hg-brand-deep` | `#0d5c38` | Hover / emphasis |
| `--hg-brand-soft` | `#f4fbf7` | Hero panels, soft highlights |
| `--hg-brand-muted` | `#e8f5ee` | Evidence / success badges |
| `--hg-link` | `#0066cc` | Citations, inline links in reports |
| `--hg-success` | `#1a7f4b` | Confidence high, optimal status |
| `--hg-warning` | `#b8860b` | Stars, moderate fit |
| `--hg-danger` | `#d70015` | Abnormal labs, safety high |
| `--hg-bg` | `#f5f5f7` | Page background |
| `--hg-surface` | `#ffffff` | Cards, panels |
| `--hg-text` | `#1d1d1f` | Body |
| `--hg-muted` | `#6e6e73` | Secondary copy |
| `--hg-border` | `#d2d2d7` | Dividers |

Do **not** use generic SaaS blue (`#0071e3`) as the primary accent on marketing or auth surfaces. Clinical green is the brand anchor.

### Typography

- **Stack:** `-apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", sans-serif`
- **Headlines:** Tight tracking (`-0.02em`), semibold/bold, max 2 lines in hero.
- **Labels:** Small caps only for true metadata (table headers, field labels), not every section eyebrow.
- **Density:** Comfortable clinical reading (`line-height: 1.45-1.5`, `max-width: 65ch` for prose).

### Shape & components

- **Radius:** 12px cards, 8px inputs, pill buttons (`border-radius: 980px`).
- **Cards:** Light border + soft shadow; green-tinted panels for confidence/hero blocks.
- **Buttons:** Primary = brand green fill, white text. Secondary = white surface + border.
- **Disclaimer blocks:** Rose-tinted border (`#ffd4d4`) on `#fff8f8` background.

### Report product patterns (carry into marketing)

- Executive summary hero with confidence level
- Clinical priorities ranked with stars
- Four-lane intervention library (botanical, nutraceutical, peptide, lifestyle)
- Sidebar navigation for long-form report sections
- Evidence passport / methodology transparency

## Site IA (public → app)

| Route | Role |
|-------|------|
| `/` | Marketing homepage |
| `/login.html` | Sign in |
| `/signup.html` | Create account |
| `/forgot-password.html` | Password reset request |
| `/reset-password.html` | Set new password |
| `/app.html` | Authenticated workspace |
| `/report.html` | Clinical report viewer |

## Design read (for landing + auth)

Reading this as: **B2B clinical SaaS landing for practitioners and researchers**, trust-first language, native CSS, clinical green palette, restrained motion.

**Dials:** `DESIGN_VARIANCE: 5` · `MOTION_INTENSITY: 3` · `VISUAL_DENSITY: 4`

## Copy rules

- Lead with explainability and evidence transparency, not "AI-powered" hype.
- Use "practitioner", "clinician", "lab data", "biomarker", "intervention library".
- Avoid: Elevate, Seamless, Revolutionize, generic purple gradients, em-dashes as decoration.
- CTAs: "Sign in", "Create account", "Open workspace" (one intent per label).

## Out of scope for taste-skill

Dashboard (`app.html`) and report viewer (`report.html`) are dense product UI. Apply brand tokens and consistency; do not run full landing-page anti-slop rules on data tables.