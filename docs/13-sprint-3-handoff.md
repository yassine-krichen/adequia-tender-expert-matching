# 13 — Sprint 3 handoff note

**Read this first if you're picking this project back up cold** (fresh chat,
cleared context, or someone else entirely). This file plus the code itself
should be enough to continue without re-deriving anything. Updated after
ADQ-19/20/22 are complete (commit `5c39710`); describes current state of the
sprint.

## Where things stand

- **Sprint 1 and Sprint 2 are done**, committed on branch `sprint-2`.
- Sprint 2's matching pipeline (coarse retrieval, hard filters, skill/sector
  scoring, working UI) was verified live against a real TDR PDF late in
  testing. That live test found and fixed two real bugs no mocked test caught
  — see `docs/report/chapters/05-sprint-2.tex`'s final subsection, or commits
  `de0ef31` (stale position accumulation on TDR reprocess) and `3bb8d5a`
  (Redis progress-state race condition). Both fixed, tested, reviewed,
  committed.
- **Sprint 3 (current, on branch `sprint-3`)**: the heaviest sprint — 50
  points, 7 stories (ADQ-19..25), backlog in `docs/scrum/sprint-3-plan.md`.
  Closes the human-in-the-loop loop: every match gets an LLM-judged score,
  anomaly detection, a cited rationale, and a reviewer can approve/reject/override it.
  - **ADQ-19, ADQ-20, ADQ-22 are done** (commit `5c39710`). Verified live
    against real running containers. That testing caught and fixed 3 additional
    bugs in the MCP/Postgres integration layer no mocked test had caught
    (MCP error handling, foreign-key insert-ordering race condition, worker
    logging misconfiguration) plus one guardrail improvement (LLM leaking
    ledger-entry IDs into French text). All fixed before code review.
  - **ADQ-24 is next** — the single riskiest story in the sprint, starting
    early per original plan's recommendation.

## The one big decision that shapes everything

The user explicitly chose to build the **real** target architecture from
`docs/03-agent-pipeline.md` — an actual compiled LangGraph `StateGraph` with
a Postgres checkpointer for durable human-in-the-loop interrupts, plus a real
MCP server for the taxonomy/historical-decisions lookups — rather than the
simpler imperative approach Sprint 2 used. Stated reason: this is for a
CV/portfolio, and the technical depth is the point, not a cost to minimize.

**This means:** ADQ-19 and ADQ-24 in particular carry meaningfully more real
engineering effort than their point values (8, 5) would suggest under a
minimal approach. That's a knowing trade the user made, not an oversight —
don't try to "simplify it back" without asking first if a future session
is tempted to.

## Architectural approach

The complete, user-approved plan (all 7 stories, shared architectural
decisions, sequencing, verification steps) is written out in full at:

```
C:\Users\user\.claude\plans\learn-and-understand-what-quirky-squid.md
```

For ADQ-19/20/22 (already done), implementation details are in:

```
C:\Users\user\.claude\plans\mutable-herding-quail.md
```

**The architecture in a nutshell** — what was built and what remains:

1. **StateGraph shape** (already compiled): `normalize_skills → score →
   (conditional) → detect_anomalies → generate_report → human_review`.
   Starts at `normalize_skills`, NOT `ingest` — this bug was fixed as part
   of ADQ-19 (the existing `graph.py` skeleton wrongly conflated ingestion
   and matching pipelines).
2. **MCP server** (`backend/app/mcp/server.py`, already built): two tools —
   `lookup_skill_taxonomy` (wraps existing normalize_skills.py logic) and
   `lookup_historical_decisions` (new, populated by ADQ-24).
3. **Citation ledger** (already built for `generate_report`): pre-sourced
   facts with real spans, LLM references ledger IDs per sentence rather than
   inventing spans. Citation-faithfulness true by construction.
4. **Guardrail prompts** (already applied): every new LLM call includes
   "this is data, not instructions" guardrail, same pattern as `extract.py`.
5. **`match_id` / thread_id** (already wired): generated client-side
   (`uuid4()`) and doubles as LangGraph checkpointer's `thread_id`. Lets
   `ReportingService.submit_review` (API process) resume a paused graph run
   that the RQ worker originally started. ADQ-24 is the first story to
   actually exercise this interrupt/resume flow.
6. **Zero-migration schema** (already done): `birth_date` added to
   `CandidateCV` JSONB blob; no Alembic work needed.
7. **Only DB migration in the plan** (already done): anomalies FK cascade
   fix (migration `0007`).

## What's actually done so far

Committed, tested, reviewed, verified live (not just claimed):

- **Commit `83de638`** — shared Sprint 3 infra (Day 1):
  - Migration `0007`: `anomalies.match_id`'s FK now has `ON DELETE CASCADE`
    (required before ADQ-20 writes to that table). Verified applied on the
    real dev DB.
  - `backend/app/mcp/server.py` — MCP server (FastMCP, streamable-HTTP),
    `lookup_skill_taxonomy` and `lookup_historical_decisions` tools. Verified
    live from inside the actual `worker` container.
  - `backend/app/mcp/setup_checkpointer.py` — one-off script, creates
    LangGraph's own Postgres checkpoint tables.
  - New deps: `langgraph-checkpoint-postgres`, `mcp`, `langchain-mcp-adapters`,
    `psycopg[binary]`.
  - `docker-compose.yml`: new `mcp` service (with healthcheck) and
    `checkpointer-setup` one-shot service.
- **Commit `5c39710`** — ADQ-19, ADQ-20, ADQ-22 (all three bundled, tested,
  reviewed, verified live against real containers):
  - **ADQ-19** (`score` node): `judge_qualitative_fit` LLM call + 
    `calibrate_against_history` MCP-backed calibration (logs sanity-check
    note, never modifies score). New weighting: `0.45*skill + 0.25*sector +
    0.30*qualitative` (was 0.6/0.4 skill/sector only).
  - **ADQ-20** (`detect_anomalies` node): 4 rule-based checks (employment
    gaps, date overlaps, expired certifications, age-at-graduation
    implausibility) + LLM plausibility pass restricted to
    `title_seniority_mismatch`/`unverifiable_claim`. New `birth_date: date |
    None` field on `CandidateCV` JSONB (zero Alembic migration needed).
  - **ADQ-22** (`generate_report` node): citation-ledger design (facts
    pre-sourced as `LedgerEntry` objects, LLM references ledger IDs,
    `Citation` objects assembled in code from what was actually referenced).
    Plain-French rationale; separate hard-filter-only branch with no LLM
    call.
  - **StateGraph fixed**: now genuinely starts at `normalize_skills` (not
    `ingest`). `matching_tasks.py` rewritten from direct function calls to
    `graph.ainvoke(...)` per candidate, Postgres checkpointer wired in for
    real.
  - **Real MCP client wired**: `MultiServerMCPClient` from `langchain-mcp-adapters`
    (dependency now used, not unused).
  - **Synthetic CV fixtures**: regenerated with birth dates; new idempotent
    `backend/scripts/backfill_cv_birth_dates.py` patches already-uploaded CV
    rows.
  - **Live testing caught 3 bugs** (plus 1 guardrail improvement, all fixed
    before code review):
    - `calibrate_against_history` had no error handling — transient MCP
      failure could fail entire TDR matching run. Fixed with scoped try/except.
    - `AnomalyModel`/`MatchResultModel` FK insert-ordering bug: autoflush
      could insert anomalies before parent match_result existed. Fixed with
      explicit `session.flush()` between inserts.
    - RQ worker never called `configure_logging()`, so INFO-level logs
      (including `calibrate_against_history` notes) were invisible. Fixed.
    - LLM was leaking internal ledger-entry IDs into French rationale text
      despite structural citation handling. Fixed guardrail prompt.
- **Commit `be0b93e`** — the last Sprint 2 commit (report chapter + matching
  UI screenshots), inherited from `sprint-2` as `sprint-3`'s branch point —
  not itself part of Sprint 3's work.

## What's next, in order

~~ADQ-19, ADQ-20, ADQ-22~~ **done**. Remaining stories, per the plan's
sequencing (this is the load-bearing part — re-read the full plan file's
"Sequencing" section before starting):

1. **ADQ-24** (HITL interrupt + `historical_decisions` write-back) — **do
   this next**. **This is the single riskiest story in the sprint** — first
   time this codebase runs a durable cross-process LangGraph interrupt/resume,
   first time two separate Postgres drivers (asyncpg + psycopg) run side by
   side. Start it with slack in the schedule, not at the last minute. Needs
   ADQ-22 (done).
2. **ADQ-21** (synthetic anomaly injection eval) — only needs ADQ-20 (done),
   can run in parallel with ADQ-24.
3. **ADQ-23** (injection-resistance tests) — needs 19+20+22 (all done), can
   run in parallel with anything.
4. **ADQ-25** (report view page) — needs ADQ-22 (done) + ADQ-24. Last story,
   and it's the sprint's demoable slice.

**If something has to slip**, prefer cutting ADQ-21 or ADQ-23 (both leaves,
nothing depends on them) over ADQ-24/25 — the sprint goal explicitly names
the working review flow as the deliverable.

## Extending the evals (open task, user's to schedule)

The eval harness already exists and is genuinely simple to extend — no new
code needed to add more gold-standard cases, just new fixture files.

**TDR extraction gold set** (`backend/tests/eval/fixtures/*.json`,
`test_tdr_extraction_quality.py`): only 3 of the ~11 TDR PDFs in `docs/tdrs/`
currently have a hand-verified fixture (`tdr_8.json`, `si_ci_avenant.json`,
`dp_4_modules.json`). The test auto-discovers every `*.json` in that folder
— to add one, read a real TDR's staffing/positions section once, write a
JSON file matching this shape:

```json
{
  "source_file": "docs/tdrs/<the pdf>.pdf",
  "note": "what section you read to verify this",
  "expected_positions": [
    {
      "title_contains_any": ["chef de projet"],
      "diploma_contains": "bac+5",
      "minimum_years_experience": 15
    }
  ],
  "known_limitations": ["optional: anything the extractor structurally can't get right, e.g. a title-page graphic pypdf can't read"]
}
```
Drop it in `backend/tests/eval/fixtures/`, done — `test_tdr_extraction_quality.py`
picks it up automatically via glob. Run with `uv run pytest -m eval` (not part
of the default test run — hits real LLM providers, costs real quota/time).

**CV extraction gold set**: does **not** exist yet as its own eval (there's
only the CV-*position* matching gold set,
`fixtures/matching/gold_matching_set.json`, which tests matching quality, not
raw field-extraction correctness). If you want this too, it needs a new
`test_cv_extraction_quality.py` mirroring the TDR one exactly (same
`@pytest.mark.eval`, same glob-fixture pattern), with fixtures shaped for
whatever CV fields matter most (education, certifications, experience dates —
whatever `docs/04-evaluation-metrics.md`'s "field-level F1" section names).
Recommend treating this as a **small, separate task**, not folded into any
of the 7 Sprint 3 stories' scope or points — it's valuable groundwork but
nobody budgeted it, and Sprint 3 is already the heaviest sprint.

## Small things worth remembering

- Docker containers need an explicit `docker compose up -d --build <service>`
  after any backend code change — there's no hot-reload/volume-mount dev loop
  in this setup. Forgetting this was the root cause of one production-feeling
  false start earlier (rebuilt code looked deployed but wasn't).
- This project's dev Postgres runs on host port **5433**, not 5432 (a native
  Windows Postgres service already owns 5432 on this machine).
- `docs/report/` is the LaTeX report for the internship deliverable — keep it
  in sync with real sprint outcomes as stories land, same as was just done
  for Sprint 2. There's no local LaTeX toolchain to compile it (no
  pdflatex/xelatex) — verify structurally (brace/environment balance) or ask
  the user to compile via Overleaf.
