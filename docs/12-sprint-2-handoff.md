# 12 — Sprint-2 handoff note

**This is a one-time handoff, not a permanent doc, and is now stale.** Written at the tail
end of the sprint-1 chat session so a fresh sprint-2 chat could read one file
and be current. The final state of Sprint 2 is now documented in
`docs/report/chapters/05-sprint-2.tex` and `docs/01-architecture.md`; refer
to those instead for the actual delivered state.

## What's shipped

`docs/11-sprint-1-dev-guide.md` has the authoritative "done vs. still
stubbed" table — read that first, don't duplicate it here. Since that
guide's last content update, this session added on top of it:

- **Async TDR pipeline**: `POST /tdrs` returns immediately, extraction runs
  on an RQ worker (`backend/app/worker/tasks.py`), frontend polls
  `GET /tdrs/{id}/status` and shows live stage text instead of a static
  spinner. `GET /tdrs/{id}` now actually implemented.
- **Eval harness**: `backend/tests/eval/` — hand-verified fixtures +
  live-LLM parametrized test, run explicitly via `uv run pytest -m eval`
  (excluded from the default suite — costs real API quota). This is the
  answer to "how do I keep improving extraction quality": when an
  extraction is wrong, add/update a fixture with the correct answer (one
  human read, done once), tune retrieval/prompt in
  `backend/app/features/pipeline/nodes/extract.py`, re-run
  `pytest -m eval` — every previously-fixed document gets re-checked
  automatically, so a new tuning pass can't silently re-break an old one.
  Growing this (more fixtures, more real TDR samples) is the actual lever
  for extraction quality now, not manual eyeballing.
- **Theme migration**: Tailwind v3 → v4, palette replaced with a
  template-derived one (light/dark toggle via `next-themes`, hotkey `d`).
  `docs/07-branding.md` was refreshed this session to match — if it looks
  wrong, the CSS (`frontend/src/styles/globals.css`) is the source of
  truth, not the doc.
- **File upload**: `frontend/src/common/components/file-upload.tsx` +
  vendored `frontend/src/hooks/use-file-upload.ts` (shadcn `@reui`
  registry, patched twice — see comments inline in the hook for both
  patches: a setState-during-render fix, and a silent-multi-file-drop fix).
- **Internship report**: `docs/report/` reorganized (`chapters/`,
  `assets/{logos,screenshots}/`, `notes/` — was loose files in root
  before). `chapters/04-sprint-1.tex` is now complete: async pipeline,
  eval harness, upload/theme work, and a "Live Demonstration" section with
  real screenshots. No local LaTeX toolchain to compile it — cross-checked
  `\includegraphics` filenames against the actual asset paths instead.
- **One-command local run**: `./scripts/dev.ps1` (wraps
  `docker compose up --build`, now with a `migrate` service so a fresh DB
  gets `alembic upgrade head` automatically — no more manual migration
  step before compose works). Root `README.md` and the dev guide both
  point at this now.

## Sprint 2 scope — already planned, don't re-derive it

`docs/scrum/sprint-2-plan.md` is the real backlog, already written:
**2026-07-13 → 2026-07-17, 42 points, goal = "given a TDR position and the
CV pool, produce a real ranked shortlist with sub-scores — visible in a
working matching results view."** Backlog: ADQ-10 (skill taxonomy seed),
ADQ-11 (coarse retrieval pre-filter), ADQ-12/13/14 (`normalize_skills`:
embedding retrieval, reranker, agentic retry), ADQ-15/16 (`score` node:
hard filters, weighted sub-scores), ADQ-17 (matching results page —
**the sprint-2 demoable slice**), ADQ-18 (Precision@K/Recall@K vs. the
gold matching set). Full acceptance criteria are in that file — read it,
don't ask the user to re-explain scope that's already written down.

Everything in this handoff doc (async pipeline, eval harness, theme,
upload UX, code review) happened *before* sprint 2 starts — it's
sprint-1 work that ran long, not sprint-2 work already done. Sprint 2
proper starts from ADQ-10.

## Known correctness bugs — not yet fixed

Found via an 8-angle code review this session, reported to the user, not
yet triaged/fixed. Worth picking up early in sprint-2:

1. `backend/app/worker/tasks.py` — the `try/except` in
   `run_tdr_extraction_job` only covers the extraction call itself, not
   the success-path persistence (lines after the `try` block) or `_run()`'s
   setup. A failure there leaves the TDR row stuck at `status="processing"`
   forever, no `error_message`, nothing for the frontend poll to key off.
2. `backend/app/features/tdrs/service.py:79` — `get_status` makes a
   blocking sync Redis call (`self._redis.hgetall`) inside an `async def`,
   blocking the event loop.
3. `backend/app/features/tdrs/service.py:62-67` — `upload_tdr` commits the
   placeholder row before enqueueing; if `enqueue()` itself throws, the row
   is orphaned at `status="processing"` with no job ever running against
   it.
4. `frontend/src/app/tdrs/page.tsx` — `pollUntilDone`'s `setInterval` with
   an async callback can fire overlapping requests if a single poll takes
   longer than `POLL_INTERVAL_MS` (1500ms).
5. `backend/app/database/migrations/versions/0002_tdr_status.py` —
   `downgrade()` reverts `mission_title`/`raw_text`/`extracted_json` to
   `NOT NULL` without backfilling first; will fail against any real row
   that has NULLs in those columns (i.e. any row still `"processing"`).

Lower-priority, also from that review: progress-key format duplicated as a
string literal instead of importing `_progress_key()`
(`service.py`); no DB `CHECK` constraint on `TDR.status`'s three valid
values; `use-file-upload.ts`'s duplicate-file check `return`s out of the
whole batch instead of `continue`ing past just the duplicate (only reachable
if this app ever sets `multiple: true` somewhere — it doesn't today);
`getTdrStatus`/`getTdr` missing explicit return types.

## Docs freshness

`07-branding.md` and `11-sprint-1-dev-guide.md` were both re-verified and
updated this session. Everything else under `docs/` — `01-architecture.md`,
`02-data-schemas.md`, `03-agent-pipeline.md`, etc. — was not reviewed this
session and may already be ahead of or behind actual code. Standard rule
applies: grep/read the actual code before acting on what a doc claims.
