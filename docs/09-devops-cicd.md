# 09 — DevOps, CI/CD & Hosting

Sized deliberately for a one-month internship deliverable, not a production
system — every choice below avoids infrastructure you don't have a problem
big enough to justify yet.

## Docker

One `docker-compose.yml` for local development:

```yaml
services:
  api:
    build: ./backend
    ports: ["8000:8000"]
    depends_on: [postgres, redis]
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@postgres:5432/adequia
      - REDIS_URL=redis://redis:6379

  worker:
    build: ./backend
    command: rq worker
    depends_on: [postgres, redis]

  postgres:
    image: pgvector/pgvector:pg16
    environment:
      - POSTGRES_PASSWORD=postgres
      - POSTGRES_DB=adequia
    volumes: ["pgdata:/var/lib/postgresql/data"]

  redis:
    image: redis:7-alpine

  web:
    build: ./frontend
    ports: ["3000:3000"]
    depends_on: [api]

volumes:
  pgdata:
```

Worth having even without deploying anywhere else — "clone and run" for a demo
matters, and it's the same setup you'd use if you ever needed to self-host.

## GitHub Actions

Split by cost, not just by trigger — the eval suite spends real API tokens, so
it shouldn't run on every keystroke.

**On every PR (`ci.yml`):**
- Lint/format: `ruff` + `black` (backend), `eslint` + `prettier` (frontend)
- Unit tests (`pytest`), no LLM calls — mock the LLM layer for these
- Type checks (`mypy` or `pyright`, `tsc --noEmit`)

**On merge to `main` (`build.yml`):**
- Build Docker images for `api` and `web`, push to GitHub Container Registry
  (`ghcr.io`)
- Trigger deploy (see hosting below — Vercel/Railway can auto-deploy from a
  GitHub push directly, so this step may just be "nothing to do, they're
  already watching the branch")

**Manual trigger only (`eval.yml`):**
- Full RAGAS/DeepEval suite against the gold datasets from
  `04-evaluation-metrics.md`
- Run this before any milestone/demo, and whenever you've changed a prompt or
  a scoring weight — not on every commit

## Hosting

No Kubernetes, no self-managed servers — all managed platforms with GitHub
auto-deploy:

| Component | Where | Why |
|---|---|---|
| Next.js dashboard | **Vercel** | Zero-config Next.js hosting, auto-deploys from GitHub, free tier is enough |
| Postgres + pgvector | **Supabase** | You already have Supabase experience from AegisHire — direct continuity, managed pgvector support |
| FastAPI + Redis worker | **Railway** or **Fly.io** | Docker-native, auto-deploys from GitHub, simple env var management |

This gets you a live demo URL for the defense presentation without solving
infrastructure problems this project doesn't have at this scale. If volume or
requirements ever demanded it, migrating to a heavier setup later is a clean,
separate decision — not something to pre-optimize for now.

## Secrets

API keys (LLM provider, Supabase, etc.) live in each platform's environment
variable settings (Vercel/Railway/GitHub Actions secrets) — never in the repo,
even in a private one. Add a `.env.example` with the variable names but no
values, so the setup is documented without leaking anything.
