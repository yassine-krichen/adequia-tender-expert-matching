# 07 — Branding

## Name

**AdéquIA** — from "adéquation" (French HR/consulting term for the fit between a
profile and a position) + "IA" (French for AI). Recognizable to a francophone
consulting audience without explanation, and the pun reads naturally out loud.

Alternatives considered, if you want options: *MissionFit*, *ProfilTDR*,
*Concordance*. AdéquIA is the strongest because it borrows real domain
vocabulary rather than inventing new terminology.

## Slogan

Pick one, or use different ones for different contexts (README vs. dashboard
header vs. presentation title slide):

- *"Le bon profil, pour la bonne mission."*
- *"L'expertise, retrouvée en un instant."*
- *"Chaque TDR trouve son expert."*

## Vibe

This is decision-support software for people making real staffing and
financial calls — not a consumer app. The visual language should read as
**precise and calm**, closer to audit/compliance tooling than a gamified
product. Avoid: playful iconography, celebratory animations on "high
score" results (a 93% match isn't a achievement to celebrate, it's a fact
to trust).

The app supports both light and dark mode (toggle in the UI, or press `d`
outside a text field — see `frontend/src/common/components/theme-provider.tsx`),
it is not dark-only.

## Color palette

**Source of truth is `frontend/src/styles/globals.css`** (CSS custom
properties, `oklch()`, `:root` = light / `.dark` = dark) — this table is a
human-readable summary, not the authority. If the two disagree, the CSS
file is right and this table is stale.

| Role | Color | Value (light) | Usage |
|---|---|---|---|
| Background/Foreground | Neutral near-white / near-black | `oklch(1 0 0)` / `oklch(0.145 0 0)` | Base background/body text (shadcn neutral scale, not a fixed charcoal) |
| Primary | Vivid pink/magenta | `oklch(0.518 0.253 323.949)` | Primary actions, AI-generated content (scores, rationale) |
| Success | Emerald | `--color-emerald-500` | Approved, high compatibility |
| Info | Violet | `--color-violet-500` | Verified/grounded states, citations, "matched" indicators |
| Warning | Yellow | `--color-yellow-500` | Non-blocking anomaly |
| Destructive | Red | `oklch(0.577 0.245 27.325)` | Blocking anomaly, hard filter failure |
| Muted | Neutral gray | `oklch(0.556 0 0)` | Secondary text, disabled states |

Corner radius: `0.625rem` base (`--radius`), scaled per component via
`--radius-sm/md/lg/xl/2xl/3xl/4xl` — not 0px.

## Typography

- **Headings**: Space Grotesk
- **Body**: Inter
- Consistent with your existing portfolio/design system — no new tooling to
  adopt mid-internship.

## Tone of voice (for UI copy and report text)

Plain, direct, no hype. The rationale text a reviewer reads should sound like
a careful colleague explaining their reasoning, not a marketing tool praising
a candidate. E.g.:

> "Ce profil correspond à 93% des critères demandés. Expérience et
> certifications conformes aux exigences. Aucune anomalie détectée."

Not:

> "🎉 Excellent match! This candidate is a superstar fit for your mission!"
