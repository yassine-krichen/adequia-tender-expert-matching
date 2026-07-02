# Sprint 1 Plan

**Dates:** 2026-07-06 → 2026-07-10 (5 working days)
**Capacity:** solo developer, ~43 points committed. Deliberately front-loaded: this sprint also proves the riskiest technical integration (multi-key LLM routing across free-tier providers) end-to-end, not just the lowest-complexity setup work — flag in the Sprint 1 retro if this was over-committed.

**Sprint Goal:** Upload a real CV/TDR and see it turned into structured, extracted data end-to-end — the foundation every later sprint builds on, proven with a working (if rough) screen, not just a backend status update.

**Definition of Ready / Done:** see `definition-of-ready-and-done.md`.

## Sprint backlog

### ADQ-1 — Provision Alembic migrations for the full Postgres schema
**Epic:** devops · **Priority:** P0 · **Points:** 3

Acceptance criteria:
- [ ] Alembic initialized against `backend/app/database` (`env.py` already scaffolded)
- [ ] One migration creates every table from `docs/02-data-schemas.md`: `candidates`, `cvs`, `tdrs`, `expert_positions`, `skill_taxonomy`, `match_results`, `anomalies`, `historical_decisions`
- [ ] `pgvector` extension enabled; `skill_taxonomy.embedding` has an `ivfflat` index
- [ ] `alembic upgrade head` runs clean against a fresh `docker compose up -d postgres` instance
- [ ] Migration is reversible (`alembic downgrade -1` drops cleanly)

### ADQ-2 — Multi-provider model routing: Groq + Gemini key-pool rotation with local Ollama fallback
**Epic:** devops · **Priority:** P0 · **Points:** 8

Acceptance criteria:
- [ ] `GROQ_API_KEYS` and `GEMINI_API_KEYS` (comma-separated) parsed into key pools at startup
- [ ] Round-robin rotation within a provider's key pool on each call
- [ ] A rate-limit/quota error from one key rotates to the next key instead of failing the request
- [ ] Once all keys across both providers are exhausted, calls fall back to local Ollama (`OLLAMA_BASE_URL`)
- [ ] Extraction tier and reasoning tier are configured independently (fast/cheap vs. stronger model — `docs/01-architecture.md` model routing)
- [ ] A unit test simulates full key exhaustion and asserts the Ollama fallback fires

### ADQ-3 — Parse CV/TDR documents (text-PDF, docx) into raw text
**Epic:** ingestion-extraction · **Priority:** P0 · **Points:** 5

Acceptance criteria:
- [ ] `ingest` node accepts PDF and docx, returns raw text
- [ ] Tested against at least 3 real (anonymized) CVs and 2 real TDRs
- [ ] A corrupt/unsupported file raises a typed `DomainError`, never a silent empty string

### ADQ-4 — Spike: sample real CVs/TDRs, confirm OCR need
**Epic:** ingestion-extraction · **Priority:** P1 · **Points:** 2

Acceptance criteria:
- [ ] At least 10 real CVs and 5 real TDRs sampled and manually checked (clean text-PDF vs. scanned image)
- [ ] Written finding: is OCR fallback needed at all, with the sample proportion behind the call
- [ ] Decision recorded; a follow-up OCR story is filed only if the finding says it's actually needed

### ADQ-5 — Structured extraction for CV via Pydantic schema
**Epic:** ingestion-extraction · **Priority:** P0 · **Points:** 8

Acceptance criteria:
- [ ] `extract` node produces a valid `CandidateCV` against the schema for a clean text-PDF CV
- [ ] Every extracted field carries a `source_span`
- [ ] A failed schema validation retries extraction once before surfacing an error
- [ ] System prompt treats CV text strictly as data, never as instructions (guardrail per `docs/01-architecture.md`)
- [ ] Runs against ≥10 gold-set CVs with no unhandled exceptions

### ADQ-6 — Structured extraction for TDR + section localization
**Epic:** ingestion-extraction · **Priority:** P0 · **Points:** 8

Acceptance criteria:
- [ ] TDR is chunked, chunks embedded, top-N closest to "profils/qualifications/personnel requis" retrieved before extraction
- [ ] `extract` node produces valid `TDR` + `ExpertPosition` objects from the retrieved chunks only, not the full document
- [ ] Multi-section requirement documents are handled via a map-and-merge step over retrieved chunks
- [ ] Runs against ≥5 gold-set TDRs with no unhandled exceptions

### ADQ-7 — Bare-bones upload + extraction-preview page
**Epic:** dashboard-ux · **Priority:** P0 · **Points:** 5 · **Sprint 1 demoable slice**

Acceptance criteria:
- [ ] Candidate upload form (`POST /candidates/cv`) and TDR upload form (`POST /tdrs`) both wired to the real backend endpoints
- [ ] After upload, the page displays the extracted structured fields (plain list/JSON view is acceptable — no styling requirement yet)
- [ ] A backend error is shown on the page without crashing it (result-object pattern, `common/lib/api-client.ts`)
- [ ] Demo: upload one real CV and one real TDR live, see the extracted data on screen

### ADQ-8 — Annotate gold extraction set (kickoff, ongoing)
**Epic:** ingestion-extraction · **Priority:** P1 · **Points:** 3

Acceptance criteria:
- [ ] ≥15 CV/TDR pairs manually annotated with correct structured fields
- [ ] Annotation format matches the `CandidateCV`/`TDR` schema so it's directly usable by the eval harness later
- [ ] Schema gaps or ambiguities found while annotating are logged, not silently worked around

### ADQ-9 — Request historical staffing decisions + TDR variety from company
**Epic:** company-profile · **Priority:** P0 · **Points:** 1 · **Labels:** `needs-company-input`, `blocked`

Acceptance criteria:
- [ ] Checklist from `docs/08-company-data-checklist.md` sent to the company contact
- [ ] Explicitly requests: all employee CVs, historical staffing decisions, a range of past TDRs, any existing evaluation rubric, any existing skill taxonomy, and the data-confidentiality policy
- [ ] Tracked as blocked/`needs-company-input` until a response arrives — may carry into Sprint 2
