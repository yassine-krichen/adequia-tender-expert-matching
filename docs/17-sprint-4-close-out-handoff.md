# 17 — Sprint 4 close-out handoff

Written at the very end of the final session, on low battery, mid-close-out —
read this first if picking the project back up on another machine. Covers
what shipped, what's genuinely still open, and one real scope question that
needs an answer before the final report can be written honestly.

## What shipped this session (7 commits, all 9 backlog stories + polish)

- `36d8905` — ADQ-26/27/28: dashboard polish, real metrics page, guided tour
- `fb957c2` — candidate/TDR duplicate-row bug (pre-migration rows never
  backfilled a new unique content-hash column; found live, root-caused, fixed
  with regression tests)
- `3d99c65` — ADQ-31: LangSmith tracing (was configured in the API process
  but never in the RQ worker — where every real pipeline call actually runs —
  so it silently did nothing until this fix)
- `d0d5307` — ADQ-32: lightweight local PII masking before any cloud LLM call
- `b12520a` — ADQ-34: defense demo script
- `f306a38` — ADQ-29/30/33: real faithfulness scoring, extraction F1
  regression gates, real Cohen's kappa scoring-agreement measurement
- `7f13eef` — discretionary polish: real home page (was the unbuilt Next.js
  stub), match report identifying context, icons app-wide, browsable
  candidate/TDR history pages
- `9a35fa7` — **fix found via live user testing this session**: the match
  report's Education/Experience/Certification/Language sub-score bars were
  showing a fake 0% instead of "not scored." Root cause: those four fields
  are *intentionally* `null` in the backend (`app/domain/matching.py`'s
  `SubScores` docstring — they're hard-filter pass/fail checks, not scored
  dimensions, and null was chosen deliberately over "a fabricated placeholder
  number"). The frontend was doing `?? 0` on display, turning an honest null
  into a misleading failing score on every single match report. **This was
  not a skill-taxonomy data problem** — nothing needs to be regenerated or
  reseeded; it was a pure frontend rendering bug, now fixed.

All 9 Sprint 4 stories are done and this closes the 4-sprint, 34-story,
170-point backlog (`docs/scrum/product-backlog.md`) as officially fully
scoped and delivered.

## Real open items from live user testing (not yet actioned, or only partially)

### 1. UI has no persisted state across navigation
Reported directly by the user: "if I change pages, everything is gone."
Accurate — every page (`candidates`, `tdrs`, `matches/[id]`, etc.) uses local
`useState` + fetch-on-mount, no caching layer, no URL-encoded state, nothing
in `sessionStorage`/`localStorage` beyond the guided-tour flag. Navigating
away and back always refetches from scratch and loses any in-progress
client-side state (e.g. an uploaded-but-not-yet-run-matching TDR's in-memory
`result` object).

This is a real architectural gap, not a bug — this app was built fetch-on-
mount throughout, on purpose, per the existing `ApiResult<T>`/no-React-Query
convention (see `docs/05-frontend-dashboard.md` and every existing page).
Closing it properly means picking one of:
- Cheapest: persist the currently-viewed TDR/candidate's client state to
  `sessionStorage` so a back-navigation restores it (small, targeted fix).
  Doesn't fix cross-session persistence, but fixes "everything is gone"
  during one work session.
  candidates and TDRs are used to look up by real ID rather than by transient
  in-memory browser state (much bigger change — this is what React Query or
  a similar server-state layer exists to solve, and this project's
  `preferences.md` explicitly calls for "React Query (or equivalent) for
  server state" once local state stops being enough — this may be that
  point).
- **Recommendation**: start with the cheap `sessionStorage` fix for the
  in-progress-upload case specifically (that's the concrete pain point the
  user hit), not a full React Query migration — that's real new scope, not a
  polish item, and should be scoped/planned properly rather than bolted on
  at the very end of the internship.

### 2. Discoverability: not obvious you need to click a candidate to see the full match report
Reported directly: "how would I know I would need to click the candidate to
view the exact match details." The TDR page's per-position matches table
(`frontend/src/features/tdrs/components/tdr-positions-list.tsx`) renders
candidate names as plain links with no visual affordance beyond default link
styling — no icon, no "View match report" label, no hover cue beyond a color
change.

Fix is small and low-risk: add a visible action (e.g. a trailing chevron
icon, or an explicit "View report →" label/button per row) instead of relying
on the candidate name itself being a clickable link. Same treatment probably
worth applying to the candidates-table → candidate-detail links added in
`7f13eef`, for consistency.

### 3. "Scoring is mostly 0" — FIXED this session (see `9a35fa7` above)
Confirmed root cause and fixed live. No further action needed on this one
specifically, but see item 4 below for a related, deeper question the user's
observation surfaced.

### 4. Should the hard-filter-only fields (education/experience/certification/language) ever become real weighted scores?
The underlying design (from Sprint 2, `app/domain/matching.py`) is that only
`skill_score`/`sector_score`/`qualitative_fit_score` are real weighted
compatibility-score inputs; education/experience/certification are binary
hard filters (pass → candidate is even considered; fail → rejected outright,
never scored), and language was never wired into scoring at all beyond being
extracted. This was a deliberate, documented Sprint 2 decision, not an
oversight — but now that the frontend fix makes this visible and honest
("checked as pass/fail only, not scored") instead of hiding it behind a fake
0%, it may prompt the question of whether education/experience/certification/
language *should* become real partial-credit weighted dimensions in a future
iteration (e.g. "exceeds required experience by 3 years" scoring higher than
"exactly meets it"), rather than pure pass/fail. Flagging as a real design
question for a future sprint, not something to guess at and change
unilaterally now — it changes the compatibility-score weighting model and
needs its own planning pass.

## The one scope question that needs a real answer before the final report

The user raised, live, that the original project scope (as discussed at
kickoff, before any of the 4 sprints were planned) included a further step:
the AI evaluating whether the company should bid on a TDR at all, and
recommending how much to bid.

**Confirmed by re-reading the full backlog**: no such story exists anywhere
across all 4 sprints (`docs/scrum/product-backlog.md`, 34 stories, 170
points) or in the icebox list (`docs/06-roadmap.md`'s unscheduled-work
section). The pipeline as built and fully shipped stops at: TDR → extraction
→ matching → scoring → anomaly detection → cited rationale → human
approve/reject/override. There is no bid/no-bid recommendation, no pricing
recommendation, anywhere in the system.

This is either:
(a) scope that was verbally discussed at kickoff but never made it onto the
actual sprint-planning backlog (fell through the cracks during initial
backlog-writing, before this session's involvement), or
(b) something that was always understood to be a later/future-phase idea
beyond what the 4 sprints were ever meant to cover.

**This needs a real answer from the supervisor before the final report is
written** — see the drafted email (`docs/scratch_email_draft.md`, question
#4) which raises this directly rather than silently omitting it or silently
claiming it's done. Do not write the final report claiming this capability
exists; it does not, anywhere in the codebase.

If the answer comes back "yes, this should have been built" — this is
**new scope for a 5th sprint or a post-internship follow-up**, not something
to bolt onto Sprint 4's closed backlog retroactively. It would need its own
planning pass: what data would a bid/no-bid judgment need (cost estimates
per role? company capacity/utilization data? historical win/loss records?
none of which currently exist anywhere in this system or its gold sets), what
the output would look like, and where it fits in the existing LangGraph
pipeline (likely a new node after matching completes for all positions on a
TDR, not per-candidate).

## Also still open from earlier in the session (unrelated to the above)

- **TDR extraction field-level F1** is honestly marked `pending` in
  `docs/04-evaluation-metrics.md` and `backend/tests/eval/test_tdr_extraction_quality.py`
  (test is `@pytest.mark.skip`'d with a clear reason) — the live test
  (13 real TDR PDFs, real LLM extraction) hit a hard 15-minute timeout twice
  under free-tier LLM latency, even under good network/power conditions. CV
  extraction's equivalent number is real (F1=0.978); document-level TDR
  pass-rate (12/13, real) stands in as the current proxy. To actually get
  this number: either run it with more patience/budget (it may just need
  30-45 min of real wall-clock time, not a bug), or run it fixture-by-fixture
  instead of all 13 in one test, or use paid API access instead of free-tier
  if that ever becomes available.
- **GitHub repo secrets** (`GROQ_API_KEYS`, `GEMINI_API_KEYS`) referenced by
  `.github/workflows/eval.yml` need to actually be added via GitHub repo
  Settings → Secrets and variables → Actions before that CI workflow can run
  for real — this wasn't something achievable from this environment (no
  push access to add secrets, and `sprint-4` was never pushed to the remote
  as of this session, so the workflow isn't even registered on GitHub yet).

## Environment gotchas (still true, hit again this session)

- Docker Desktop and local Ollama do not stay running between sessions on
  this machine — check both before assuming anything works (see
  `docs/15-sprint-4-handoff.md` for the exact commands).
- Docker Desktop's daemon itself went down mid-session this time too (not
  just needing a restart — the whole `dockerDesktopLinuxEngine` pipe was
  unreachable at one point), separate from the earlier known
  container-goes-stale issue. Same fix applies: relaunch Docker Desktop,
  wait for `docker info` to succeed, then `docker compose up -d --build`.
- Free-tier LLM providers (Groq, Gemini) hit real quota exhaustion multiple
  times this session under heavy live-testing load — this manifests as very
  slow runs (falling back to local Ollama on every call) rather than clean
  errors. Budget real wall-clock patience for any live eval/matching run,
  especially right after a lot of prior live testing in the same day.

## For the final report itself

- Real, defensible numbers that exist today (all in `docs/04-evaluation-metrics.md`):
  CV extraction F1=0.978, retrieval Recall@3=1.0/Precision@3=0.33 (expected,
  k=3 shortlist with 1 true match), anomaly detection precision/recall/F1=1.0
  on 4 rule-based types, injection-resistance 5/5=100%, faithfulness=0.91/
  citation coverage=1.00, scoring-agreement Cohen's kappa=1.0 (n=2, small
  sample — will firm up as more real reviews accumulate), efficiency p50=3.52s/
  p95=4.65s per match (measured under degraded free-tier conditions, honestly
  caveated as such).
- What's missing to make the report land harder: the manual-baseline time
  estimate and any real historical staffing decisions — both requested from
  the supervisor in `docs/scratch_email_draft.md`. These are the two numbers
  that would turn "the pipeline is fast" into "this saves N hours per
  position" and "the AI's judgment matches real human decisions," which are
  the two claims that actually matter for a CV/portfolio narrative.
- Be precise about what "prod ready" means for this project (see
  `docs/15-sprint-4-handoff.md`'s "On prod ready" section, still accurate):
  fully complete, polished, and defensible academically — not hardened for
  real production traffic. No auth story exists anywhere on the backlog by
  explicit design; PII masking is lightweight/partial by explicit scope, not
  full compliance-grade.
