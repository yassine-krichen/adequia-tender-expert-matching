# 05 — Frontend Dashboard (Next.js)

## Purpose

The dashboard is where an HR reviewer actually uses this system day to day, and
where the human-in-the-loop override happens. It's also your best demo surface
for the internship defense — treat the visual polish as seriously as the
pipeline itself.

Reuse your existing freelance-portfolio aesthetic: dark theme, Space Grotesk +
Inter, zero border-radius, Framer Motion for transitions. Consistency with your
own design system is free credibility.

## UX principles (design for a reviewer with zero context)

The target user should be able to use this with no prior explanation of what a
"compatibility score" or an "anomaly" means. Concretely:

- **Component library**: shadcn/ui. Use `Tooltip`/`HoverCard` on every
  non-obvious concept — a small info icon next to "Compatibility Score," "Hard
  Filter," "Anomaly," "Citation" that explains the concept in plain language on
  hover, not engineering jargon.
- **Empty states explain, not just blank**: before a TDR is uploaded, the
  matching page should explain what will appear there once one is, not just
  show nothing.
- **First-run guided tour**: upload a TDR → see extracted positions → see
  ranked matches → understand the score → understand an anomaly flag →
  approve/override. Keep it skippable and short.
- **Plain-language report text**: the generated rationale must read naturally
  for an HR reviewer ("ce profil correspond à 93% des critères demandés,
  notamment...") — reserve technical vocabulary for your internal docs, never
  surface it in what a reviewer reads.

## Pages

### 1. Candidate CV management
- Upload/update employee CVs individually or in bulk
- Each CV shows a `last_updated` timestamp; re-uploading a CV triggers
  re-extraction and re-embedding for that candidate only
- This page is how the CV database stays current over time — see the note in
  `02-data-schemas.md` on why `total_years_experience` is computed, not stored
  static

### 2. TDR upload & breakdown
- Upload a TDR file (PDF/docx)
- Show the extracted structure: mission title, client, sector, deadline, and the
  list of required expert positions, each with its parsed requirements
  (diploma, years, certifications, languages, skills)
- Allow manual correction of extraction errors before running matching (this
  correction data is valuable — feed it back into the gold extraction set)

### 3. Matching results — per position
- For a selected TDR position, show a ranked list of candidates with:
  - Compatibility score (prominent)
  - Hard filter status (pass/fail, with reason if failed)
  - Sub-score breakdown (education, experience, certifications, sector,
    language, skills) — a small horizontal bar chart per criterion works well
  - Anomaly flags, color-coded by severity, each expandable to show the
    citation/source span
- Clicking a candidate opens the full report view

### 4. Report view (per candidate–position match)
- Full rationale text, with citations rendered as hover/click-to-reveal
  highlights pointing back into the original CV or TDR text (this is the
  explainability payoff — make it visible, not just present in the data model)
- Approve / Reject / Override controls — this is the HITL interrupt point from
  `03-agent-pipeline.md`. An override requires a short reviewer note, which gets
  stored and feeds `historical_decisions`

### 5. Metrics dashboard
- Pulls from the eval harness output (`04-evaluation-metrics.md`)
- Extraction F1, retrieval precision/recall, scoring agreement, anomaly
  detection precision/recall, time saved, cost per CV
- This page is as much for your defense presentation as for actual company use —
  design it to be screenshot-able

### 6. (Stretch) Company profile view
- Only build after core pages are solid. Static-ish view of the company
  capability data (past project references, aggregate specialties, firm
  certifications) feeding the bid/no-bid decision from the company side.

## API contract (FastAPI ↔ Next.js)

Keep this thin and typed — mirror the Pydantic models from
`02-data-schemas.md` directly as the API response shapes so there's no
translation layer to maintain.

```
POST /candidates/cv             — upload/update a candidate's CV, triggers re-extraction
GET  /candidates                — list candidates + last_updated
POST /tdrs                     — upload + extract a TDR
GET  /tdrs/{tdr_id}            — get parsed TDR + positions
POST /tdrs/{tdr_id}/match      — run matching for all/selected positions
GET  /positions/{position_id}/matches   — ranked match results for a position
GET  /matches/{match_id}       — full match result incl. report + citations
POST /matches/{match_id}/review — submit approve/reject/override decision
GET  /metrics                  — current eval harness output
```

## State/data fetching

Given the volume is modest (internal tool, one company's TDR pipeline), plain
fetch + React state or a lightweight data-fetching library is enough — no need
for heavy client state management. Keep it simple; the complexity budget for
this project belongs in the AI pipeline, not the frontend plumbing.
