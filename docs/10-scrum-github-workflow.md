# 10 — Scrum & GitHub Workflow

## Methodology: Scrum, with 1-week sprints

Classic Scrum assumes a team syncing daily over 2-week sprints — a mismatch
for a solo, one-month project. Kanban would technically fit a solo developer
better (no team to synchronize with), but Scrum is the more recognizable
methodology for a resume/interview story, and **1-week sprints instead of
2-week ones** resolves the actual mismatch: your 4-week roadmap
(`06-roadmap.md`) becomes exactly 4 sprints.

Per sprint:
- **Sprint planning** (start of week): pick issues from the backlog into the
  sprint, sized to what's realistic in 5 working days
- **Daily "standup"**: even solo, write a 2-3 line log at the end of each day
  (what shipped, what's blocked) — either as a GitHub issue comment on a
  running "Sprint N log" issue, or in your own notes. This is what lets you
  reconstruct a coherent story for the defense later.
- **Sprint review/demo** (end of week): a short recorded or live walkthrough of
  what actually works, matched to the sprint goal
- **Sprint retro** (end of week): 3 bullets — what went well, what didn't,
  what changes next sprint

## Epics (map directly to `06-roadmap.md` weeks + cross-cutting concerns)

| Epic | Covers |
|---|---|
| `epic: ingestion-extraction` | Document parsing, TDR section localization, structured extraction, Pydantic/Postgres schema |
| `epic: matching-engine` | Skill taxonomy, embeddings, coarse retrieval, hybrid scoring, LangGraph wiring |
| `epic: anomaly-detection` | Rule-based checks, LLM plausibility pass, synthetic anomaly injection framework |
| `epic: reporting-explainability` | Report generation, citations, RAGAS/DeepEval harness |
| `epic: dashboard-ux` | Next.js pages, shadcn/ui components, onboarding, tooltips |
| `epic: devops` | Docker, GitHub Actions, hosting, secrets |
| `epic: company-profile` | Stretch scope — firm-level capability check |

## GitHub labels

**Type** (one per issue):
`type: epic` · `type: story` · `type: task` · `type: bug` · `type: spike` · `type: chore`

**Priority** (one per issue):
`P0-blocker` · `P1-high` · `P2-medium` · `P3-low`

**Component** (one or more per issue):
`component: backend` · `component: frontend` · `component: ai-pipeline` ·
`component: data` · `component: devops` · `component: docs`

**Sprint** (one per issue, once planned):
`sprint-1` · `sprint-2` · `sprint-3` · `sprint-4`

**Status flags** (as needed):
`blocked` · `needs-company-input` (use this specifically for anything waiting
on an item from `08-company-data-checklist.md`)

## Story points

Fibonacci-ish, small scale since it's solo work: `1` `2` `3` `5` `8`. If
something feels bigger than an 8, it's actually an epic or needs to be split
into multiple stories before it goes in a sprint.

## Board columns (GitHub Projects)

`Backlog` → `Sprint Backlog` → `In Progress` → `In Review` → `Done`

Keep "In Review" meaningful even solo — it's where you self-check against the
Definition of Done before calling something finished, and it's a natural place
to note what you'd want a real reviewer to check.

## Definition of Done

An issue isn't `Done` until:
- [ ] Code is merged to `main` (or the relevant feature branch is merged)
- [ ] Lint/type checks pass in CI
- [ ] If it touches the pipeline: relevant eval metric checked, not just "it ran"
- [ ] If it's user-facing: has a tooltip/explanation per the UX principles in
      `05-frontend-dashboard.md`, not just a raw number on screen
- [ ] Noted in the sprint log

## Issue templates

**Story template:**
```
### Context
Which epic, and why this matters (link back to a spec file if relevant).

### Acceptance criteria
- [ ] ...
- [ ] ...

### Notes
Anything blocking, or any company-data dependency (tag `needs-company-input`).
```

**Bug template:**
```
### What happened

### Expected behavior

### Repro steps

### Severity
P0 / P1 / P2 / P3
```

## Example: first sprint's issues, epic-tagged

To get you started creating real issues from day one:

- `[epic: ingestion-extraction]` Set up FastAPI skeleton + Postgres schema — `P0` `3pts`
- `[epic: ingestion-extraction]` Parse CV/TDR PDFs and docx — `P0` `5pts`
- `[epic: ingestion-extraction]` Structured extraction for CV via Pydantic schema — `P0` `8pts`
- `[epic: ingestion-extraction]` Structured extraction for TDR + section localization — `P0` `8pts`
- `[epic: ingestion-extraction]` Annotate gold extraction set (start ongoing) — `P1` `5pts`
- `[epic: devops]` Docker Compose local dev setup — `P1` `2pts`
- `[epic: company-profile]` Request historical staffing decisions from company — `P0` `1pt` `needs-company-input`
