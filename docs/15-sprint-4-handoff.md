# 15 — Sprint 4 handoff note

**Read this first if you're picking this project back up cold** (fresh
chat, cleared context, or someone else entirely). This file plus the code
itself should be enough to start Sprint 4 without re-deriving anything.
Written at the very start of Sprint 4, before any of its stories have
started.

## Where things stand

- **Sprints 1, 2, and 3 are all done**, each on its own branch
  (`sprint-1`, `sprint-2`, `sprint-3`). Sprint 3 in particular closed the
  human-in-the-loop loop: every match gets an LLM-judged score, anomaly
  detection, a cited French rationale, and a durable approve/reject/
  override step that survives a real process boundary (RQ worker starts a
  match, the API resumes it later via a LangGraph Postgres checkpointer).
  Full detail in `docs/13-sprint-3-handoff.md` and
  `docs/14-sprint-3-summary.md` (the latter is a clean narrative retro, no
  prior context needed) — the report's Chapter 6
  (`docs/report/chapters/06-sprint-3.tex`) covers the same ground for the
  internship deliverable.
- **`sprint-4` branch already created**, branching off `sprint-3`'s final
  commit (`0e8f260`) — correctly this time; a mid-Sprint-3 mistake where
  Day-1 infra briefly landed on the wrong branch was caught and fixed, and
  this sprint starts clean from the start. Just check out `sprint-4` and
  go, no branch setup needed.
- **34 stories, 170 points across all 4 sprints, per
  `docs/scrum/product-backlog.md`.** Sprint 4 is the last sprint on the
  plan — after it, there is no more scoped core-system work, only the
  icebox (explicitly unscheduled, see below).

## Sprint 4 goal and backlog

Full backlog with acceptance summaries is in `docs/scrum/sprint-4-plan.md`
— read it in full before planning. Quick summary (35 points, 9 stories):

| ID | Story | Points |
|---|---|---|
| ADQ-26 | Upgrade Sprint 1-3 pages to the styled dashboard (candidates + TDR pages, empty states, tooltips) | 5 |
| ADQ-27 | Metrics dashboard page (pulls real eval-harness output) | 5 |
| ADQ-28 | First-run guided tour | 3 |
| ADQ-29 | Wire RAGAS faithfulness/groundedness eval | 5 |
| ADQ-30 | Start DeepEval CI regression suite | 5 |
| ADQ-31 | LangSmith/Langfuse tracing end-to-end | 2 |
| ADQ-32 | Lightweight local PII pre-processing before cloud LLM calls | 5 |
| ADQ-33 | Final metrics pass + documented methodology | 3 |
| ADQ-34 | Defense rehearsal prep (trace screenshot, metrics table, demo script) | 2 |

Sprint goal per the plan: "Full dashboard polish, remaining pages, eval
rigor, and defense-ready deliverables." This is explicitly framed as the
wind-down/polish sprint after Sprint 3's peak — no new core pipeline
stories are planned.

## On "prod ready"

If the instruction for this session is to get the whole app "finished and
prod ready," be clear-eyed about what that actually means for *this*
project versus what Sprint 4's backlog covers. Sprint 4 as scoped delivers:
a polished, fully-navigable dashboard; a real metrics page with real
numbers; a guided first-run tour; RAGAS/DeepEval-backed evaluation rigor
with an actual CI regression gate; end-to-end tracing; a lightweight
(not full) PII-masking pass; and defense-day materials. It does **not**
include: real authentication (`reviewer_id` is still hardcoded
`"anonymous"` everywhere, by explicit Sprint 3 design — no auth story
exists anywhere on the 4-sprint backlog), a production deployment
pipeline beyond the existing `docker-compose.yml` dev setup, load/scale
testing, or hardening against anything beyond the guardrail/injection work
already done. This is an internship portfolio project defended
academically (`docs/00-overview.md`, `docs/06-roadmap.md`), not a system
being handed to real users — "prod ready" here should be read as
**"fully complete, polished, and defensible,"** not "ready for production
traffic with real candidates' data." If the user actually wants
production-grade hardening (real auth, secrets management, real PII
compliance beyond ADQ-32's lightweight version, deployment automation
beyond docker-compose), that is new scope beyond the existing 4-sprint
backlog and should be raised explicitly, not silently assumed or silently
skipped.

The icebox (`product-backlog.md`, explicitly unscheduled, build only after
the core system is stable) has: a company-capability data model, a
company-profile dashboard page, auto-formatted CV annex generation, and
the *full* on-device PII pipeline (ADQ-32 ships a lighter cloud-side
version this sprint). None of this is Sprint 4's job unless explicitly
requested.

## Technical context Sprint 4 will need

- **`docs/04-evaluation-metrics.md`** was just refreshed (this session) to
  reflect exactly what eval infrastructure exists today — read its status
  box before starting ADQ-29/30/33, it names precisely what's built vs.
  what those three stories still need to add.
- **`.github/workflows/eval.yml`** currently runs `pytest tests/eval` with
  no `-m eval` override, while `pyproject.toml`'s `addopts = "-m 'not
  eval'"` applies globally — this likely means the workflow deselects
  every eval test and silently runs zero of them. This was flagged, not
  fixed, during Sprint 3 (out of scope for ADQ-23 at the time). **ADQ-30
  (DeepEval CI wiring) is the natural place to fix this** as part of
  standing up the regression suite, not a separate ticket.
- **`docs/05-frontend-dashboard.md`** is the spec ADQ-26/27/28 should
  build against — it was written before any of the actual UI existed, so
  cross-check its recommendations against what Sprint 2/3 actually built
  (the `tdrs/page.tsx` Tooltip/Badge patterns, the `match-report-view.tsx`
  review flow) rather than treating it as ground truth on its own.
- **No frontend test runner exists** (`frontend/package.json` has no
  vitest/jest/testing-library) — confirmed during Sprint 3, still true.
  Live/manual verification via the dev server (or driving a real browser
  if that tooling is available in the session) is this project's
  established practice for frontend work, not a gap to silently accept.
- **`app/features/reporting/service.py`'s `ReportingService`** already
  builds its own `ModelRouter`/`MultiServerMCPClient` in its constructor,
  and `submit_review` builds a fresh `AsyncPostgresSaver`+compiled graph
  inline per request — this is the established pattern for anything that
  needs LLM/checkpointer access from the API process; don't introduce a
  different DI pattern without a clear reason.

## Environment gotchas (all hit repeatedly this session, expect them again)

- **Docker Desktop does not stay running between sessions on this
  machine.** Check `docker compose ps` (or `docker info`) before assuming
  anything is up; if the daemon itself is down,
  `Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"` and
  wait ~10-30s for `docker info` to succeed before `docker compose up -d`.
- **Local Ollama does not stay running either** (needed for embeddings —
  coarse retrieval, skill normalization, sector scoring all depend on it).
  Check `curl http://localhost:11434/api/tags`; if it fails,
  `Start-Process "ollama" -ArgumentList "serve" -WindowStyle Hidden` and
  wait a few seconds. A matching run without this fails fast with a
  `ConnectionError` in the worker logs — not a code bug, just start Ollama.
- **Always `docker compose up -d --build`**, not `up -d` alone, after any
  backend/frontend code change — this project has no source bind mount,
  a plain `up -d` or `restart` serves stale code silently.
- **Free-tier LLM providers are genuinely flaky** — expect Gemini 503
  "high demand" errors and Groq key-pool rotation through
  `BadRequestError`s during real runs. The router already retries/rotates
  through this; a real matching run over several positions can take
  several minutes and needs patience, not a restart.
- **Port 3000 can get stuck held by a stray leftover Node process** from
  an earlier local `npm run dev` session — if `docker compose up -d web`
  fails to bind or `http://localhost:3000` doesn't look right, check
  `netstat -ano | grep :3000` before assuming the container itself is
  broken.
- **LangGraph logs a `Deserializing unregistered type ...` warning** for
  every domain object (`ExpertPosition`, `Anomaly`, `CandidateCV`, etc.)
  read back from a checkpoint — this is a forward-compatibility warning
  from the checkpoint library, not an error, and was left as-is (not
  fixed) this sprint. Safe to ignore; would need
  `allowed_msgpack_modules` registration if it's ever promoted to a hard
  block in a future `langgraph` version.

## How this project actually works (if this is a fresh session with no memory of prior ones)

- **Explore → Plan → user approval → implement → test → review → commit**,
  every non-trivial story. Plan mode was used for every story or bundle of
  stories in Sprint 3, with explicit `AskUserQuestion` check-ins at real
  design forks (not for every small decision — only where a wrong guess
  would be costly to unwind).
- **Live verification is non-negotiable, not a nice-to-have.** Every
  single Sprint 3 story that touched an LLM, a database write path, or a
  real deployment target had at least one real bug that a fully green
  mocked test suite did not catch (six for six, see
  `docs/14-sprint-3-summary.md`'s track record). Budget real time for
  this on every Sprint 4 story that touches the LLM/eval/tracing/deploy
  surface — which is most of them.
- **Bundling multiple stories into one implementation pass is an
  established, explicitly-approved pattern on this project** when the
  stories share enough architecture/testing surface that planning them
  together is more efficient than three separate round-trips (this is
  exactly how ADQ-19/20/22 and later ADQ-21/23/25 were done in Sprint 3).
  Sprint 4's stories are less interdependent than Sprint 3's were, though
  — several are genuinely independent (ADQ-31 tracing, ADQ-32 PII masking,
  ADQ-34 defense prep don't block or depend on each other) and can
  reasonably be parallelized or batched by area (frontend: 26/27/28; eval:
  29/30/33; ops/docs: 31/32/34) rather than forced into one giant pass.
- **Commit only when explicitly asked**, one logical unit of work per
  commit, Conventional Commits style, matching the existing history
  exactly (`git log --oneline` on any branch shows the convention).
