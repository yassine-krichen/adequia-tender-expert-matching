# 11 — Sprint 1 Dev Guide

What's actually implemented after Sprint 1, how to run it locally, and how
to manually test the upload → extraction flow. Written for picking this
project back up cold — read this before `03-agent-pipeline.md` if you just
want to run the thing.

## What's done vs. still stubbed

**Done (ADQ-1 through ADQ-7):**

| Area | File(s) | What it does |
|---|---|---|
| DB schema | `backend/app/database/models.py`, `migrations/versions/0001_initial_schema.py` | All 8 tables, pgvector + ivfflat index |
| LLM routing | `backend/app/common/llm/{key_pool,router}.py` | Round-robin Groq/Gemini keys, cooldown on rate-limit, falls back to Ollama when both pools exhausted |
| Document parsing | `backend/app/features/pipeline/nodes/ingest.py` | `extract_raw_text()` — PDF (pypdf) + docx (python-docx), typed errors on corrupt/unsupported files |
| CV extraction | `backend/app/features/pipeline/nodes/extract.py` | `extract_cv()` — guardrailed prompt, retry-once, `total_years_experience` computed from dates (not LLM-reported) |
| TDR extraction | same file | `extract_tdr()` — chunk + embed + retrieve top-N + per-chunk extract + map-merge |
| Upload endpoints | `backend/app/features/{candidates,tdrs}/{service,router}.py` | `POST /candidates/cv`, `POST /tdrs` — parse, extract, persist, return |
| Upload/preview pages | `frontend/src/app/{candidates,tdrs}/page.tsx` | Real upload form + extracted-field display |

**Manual/ongoing, not code:** ADQ-8 (gold-set annotation — keep annotating past the 6 synthetic CVs currently in `docs/cvs/synthetic/`), ADQ-9 (waiting on company data response).

**Still `NotImplementedError` (Sprint 2+):** `normalize_skills`, `score`, `detect_anomalies`, `generate_report` pipeline nodes; `list_candidates`, `get_tdr`, `run_matching` service methods; the matching/report/metrics dashboard pages. `backend/app/features/pipeline/graph.py`'s LangGraph wiring exists but nothing runs it yet — Sprint 1's upload flow calls `extract_cv`/`extract_tdr` directly, not through the graph.

## One-time setup

**Prerequisites:** Docker Desktop, Python 3.12 (via `uv`, not a system install — `pip install uv` if you don't have it), Node 20+, `pnpm`. Optional: [Ollama](https://ollama.com) if you want the fallback tier to actually work instead of just erroring.

```bash
# 1. Backend env
cd backend
cp .env.example .env
# edit .env: paste real GROQ_API_KEYS / GEMINI_API_KEYS (comma-separated,
# no spaces). Model names are already filled in with sensible free-tier
# defaults per provider — see "Picking a model name" below if you want to
# change them, or if you're going Ollama-only with no keys yet.

# 2. Frontend env
cd ../frontend
cp .env.example .env   # default NEXT_PUBLIC_API_URL=http://localhost:8000 is fine

# 3. Postgres + Redis (host port 5432 is taken by a native Postgres
# install on this machine — docker-compose.yml maps 5433:5432 instead;
# DATABASE_URL in .env.example already matches)
cd ..
docker compose up -d postgres redis

# 4. Python deps + migrations
cd backend
uv sync
uv run alembic upgrade head

# 5. Node deps
cd ../frontend
pnpm install
```

### Picking a model name

Groq, Gemini, and Ollama don't share a model-naming scheme, so each gets
its own setting per tier (`{PROVIDER}_EXTRACTION_MODEL` /
`{PROVIDER}_REASONING_MODEL`, 6 vars total) — the router resolves the
right one for whichever provider actually ends up serving a given call,
instead of reusing one string everywhere.

`.env.example` ships with real, currently-valid free-tier defaults:

| Var | Default | Why |
|---|---|---|
| `GROQ_EXTRACTION_MODEL` | `llama-3.1-8b-instant` | Cheapest + most permissive free-tier rate limit (14,400 req/day) |
| `GROQ_REASONING_MODEL` | `llama-3.3-70b-versatile` | Flagship, stronger judgment |
| `GEMINI_EXTRACTION_MODEL` | `gemini-2.5-flash-lite` | Cheapest free-tier Gemini model |
| `GEMINI_REASONING_MODEL` | `gemini-2.5-flash` | Stronger free-tier Gemini model — `gemini-2.5-pro` is paid-only, not usable here |
| `OLLAMA_EXTRACTION_MODEL` | `hermes3:3b` | Whatever you've pulled locally |
| `OLLAMA_REASONING_MODEL` | `hermes3:3b` | Same — pull a bigger local tag later if you want a real reasoning-tier split locally too |

If you're going Ollama-only with no Groq/Gemini keys yet, leave
`GROQ_API_KEYS`/`GEMINI_API_KEYS` empty (both pools report exhausted
immediately, no error, falls straight through to Ollama) and just make
sure the Ollama tags above are actually pulled:
```bash
ollama pull hermes3:3b
ollama pull nomic-embed-text   # needed regardless — this is EMBEDDING_MODEL
```

## Running it

Two ways — pick one, don't mix (both would try to bind the same ports).

**A. Host-run backend, host-run frontend (fastest iteration):**
```bash
# terminal 1
cd backend
uv run uvicorn app.main:app --reload --port 8000

# terminal 2
cd frontend
pnpm dev
```
API docs (Swagger UI, useful for testing endpoints directly): http://localhost:8000/docs
Dashboard: http://localhost:3000

**B. Full Docker Compose** (also builds/runs `api`, `worker`, `web` containers):
```bash
docker compose up --build
```
Same URLs. `worker` isn't actually used yet (Sprint 1's uploads run synchronously) — it'll start but sit idle.

## Manual test — the Sprint 1 demo

1. Open http://localhost:3000/candidates
2. Upload one of the synthetic CVs from `docs/cvs/synthetic/` (mix of PDF/docx, e.g. `nadia-ben-salah.pdf` or `karim-trabelsi.docx`)
3. Confirm extracted fields render: name, education, experience, skills, computed years of experience, plus the raw JSON in the collapsible section
4. Open http://localhost:3000/tdrs
5. Upload one of the real TDRs from `docs/tdrs/` (the `.docx` ones parse faster than the 193-page PDF)
6. Confirm mission title, client, sector, and extracted expert positions render
7. Try an unsupported file (e.g. a `.txt`) or a corrupted one on either page — confirm you get an inline error message (`role="alert"`), not a crashed page

If nothing renders and you get a 500, check the backend terminal — most likely cause is Ollama not running/model not pulled (if you're relying on the fallback), or a genuinely invalid/expired API key.

## Automated tests

```bash
# backend — from backend/
uv run pytest tests/ -v
uv run ruff check .
uv run mypy app

# frontend — from frontend/
pnpm lint
pnpm type-check
pnpm build
```

All of these were green as of the last Sprint 1 commit. The pytest suite mocks every LLM/embedding call (fake routers) — it does not require real API keys or Ollama to pass, only the manual test above does.

## Known gotchas

- **Port 5432**: a native Postgres install already listens there on this machine. Docker's container uses 5433 on the host instead (see `docker-compose.yml`) — don't change it back without checking `netstat -ano | grep 5432` first.
- **`OLLAMA_BASE_URL`**: `.env`'s `http://localhost:11434` is correct for the host-run backend (option A above). Full Docker Compose (option B) overrides it to `http://host.docker.internal:11434` internally for the `api`/`worker` containers — don't need to touch this yourself either way.
- **`backend/.env` and `frontend/.env` are gitignored** — every teammate/session needs their own copy from `.env.example`.
