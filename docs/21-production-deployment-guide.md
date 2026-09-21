# 21 — Production deployment guide (self-hosted, on ST2i's server)

Written for the day you're physically at ST2i deploying this on their own
server. `docs/09-devops-cicd.md` describes a different plan (managed
platforms — Vercel/Supabase/Railway) written earlier when the deployment
target was assumed to be cloud-managed. That's superseded by this guide if
you're deploying to their own on-prem/self-hosted server instead — keep
`09` for context on the original thinking, but follow this doc for the
actual on-site deployment.

The stack (`docker-compose.yml`) already runs correctly as-is for local
dev. Production on a real server needs a small, specific set of additions:
a reverse proxy with HTTPS, a fix for how containers reach Ollama on
Linux, secrets that live only on the server, restart policies, and a
backup plan for Postgres. None of this is a rewrite — it's an overlay.

---

## 0. Before you go — what to bring/know

- This repo, on the branch that ends up merged to `sprint-1` (the
  project's `main`).
- The real `backend/.env` and `frontend/.env` values are **not** in git —
  bring your working local `.env` files (or regenerate from
  `backend/.env.example` / `frontend/.env.example`) so you're not stuck
  retyping 5 Groq keys and 5 Gemini keys from memory on-site.
- Know the server's OS ahead of time if possible (assume Linux below —
  flag if it's actually Windows Server, the Ollama/Docker steps differ).
- Ask whether they're giving you a domain name pointed at the server. If
  not, you'll deploy on the bare IP with self-signed HTTPS or plain HTTP
  behind their firewall — still doable, just note it as a follow-up ("get
  a real domain + TLS cert") rather than a blocker.

---

## 1. Server prerequisites

- **Docker Engine + Docker Compose plugin** (`docker --version`,
  `docker compose version`). Install via Docker's official convenience
  script if missing: `curl -fsSL https://get.docker.com | sh`.
- **RAM**: budget at least 8 GB total. Postgres + Redis + 3 Python
  services (api/worker/mcp) + Next.js is a few GB; Ollama running
  `hermes3:3b` (~2 GB) and `nomic-embed-text` (~275 MB) on the same box
  adds real memory pressure. 16 GB is more comfortable if Ollama runs
  here rather than a separate machine.
- **Disk**: a few GB for Docker images/volumes, plus Postgres data growth
  over time (CVs/TDRs/embeddings — small at this project's scale, not a
  real concern yet).
- **Ollama installed natively on the host** (not in Docker — this matches
  the existing architecture, which already assumes Ollama is a separate
  local process, see `OLLAMA_BASE_URL`'s comment in `docker-compose.yml`):
  ```bash
  curl -fsSL https://ollama.com/install.sh | sh
  ollama pull hermes3:3b
  ollama pull nomic-embed-text
  ```
  The official installer sets up a `systemd` service, so Ollama survives
  a reboot automatically — confirm with `systemctl status ollama`.

---

## 2. The one real code-adjacent fix: `host.docker.internal` on Linux

`docker-compose.yml` points every backend service at
`OLLAMA_BASE_URL=http://host.docker.internal:11434`. That hostname
resolves automatically on Docker Desktop (Mac/Windows) — which is what
this project has been developed on — but **does not resolve by default on
native Linux**, which a company server almost certainly runs. Fix it with
one addition, don't touch the tracked dev compose file — add a prod
override instead:

```yaml
# docker-compose.prod.yml (new file, server-only, not meant for local dev)
services:
  api:
    extra_hosts:
      - "host.docker.internal:host-gateway"
    restart: unless-stopped
  worker:
    extra_hosts:
      - "host.docker.internal:host-gateway"
    restart: unless-stopped
  mcp:
    extra_hosts:
      - "host.docker.internal:host-gateway"
    restart: unless-stopped
  migrate:
    restart: "no"
  checkpointer-setup:
    restart: "no"
  postgres:
    restart: unless-stopped
    ports: []          # don't expose 5433 publicly on a real server
  redis:
    restart: unless-stopped
    ports: []          # don't expose 6379 publicly either
  web:
    restart: unless-stopped
```

`extra_hosts: host-gateway` is the standard, supported way (Docker
20.10+) to make `host.docker.internal` resolve on Linux — no code change
needed anywhere in the app itself, this is purely a compose-level fix.

Run everything with both files layered:
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

---

## 3. Reverse proxy + HTTPS

Nothing in this stack currently terminates TLS — `web` serves plain HTTP
on 3000, `api` on 8000. Don't expose those ports directly to the internet.
Put a reverse proxy in front. **Caddy** is the least-effort option if
you have a real domain (automatic Let's Encrypt, ~10 lines of config):

```
# Caddyfile
adequia.st2i.example {
    reverse_proxy /api/* localhost:8000
    reverse_proxy /* localhost:3000
}
```

(Adjust the API path prefix to match how the frontend actually calls it —
see the `NEXT_PUBLIC_API_URL` note in section 4, since that decision has
to be made *before* building the frontend image, not after.)

If there's no domain yet, run Caddy/Nginx with a self-signed cert or just
serve plain HTTP restricted to the company's internal network/VPN — don't
block the deployment on getting a domain, just flag it as a follow-up.

Only open 80/443 (or whatever the proxy uses) on the server's firewall.
Everything else (`8000`, `3000`, `5433`, `6379`, `8100`) should stay
internal-only, which the `ports: []` overrides above already handle for
Postgres/Redis — `api`/`web`'s ports still need to stay published for the
proxy to reach them, just not exposed further than that via the firewall.

---

## 4. Secrets and environment — real but important gotcha on the frontend

`backend/.env` and `frontend/.env` get created on the server directly,
same pattern as local dev (`scripts/dev.ps1`'s "copy from `.env.example`,
fill in real values" flow) — never commit real values.

**The gotcha**: `frontend/.env`'s `NEXT_PUBLIC_API_URL` is a
build-time-baked Next.js variable (`frontend/src/common/lib/api-client.ts`
reads it via `process.env.NEXT_PUBLIC_API_URL`) — it gets compiled into
the JS bundle at `docker compose build`, not read at runtime. That means:

1. Decide the real public API URL/path (e.g.
   `https://adequia.st2i.example/api`) **before** building.
2. Set it in `frontend/.env`.
3. Build the `web` image *after* that's set — if you change it later,
   you must rebuild `web`, restarting the container alone won't pick up
   the new value.

Everything else in `backend/.env` (Groq/Gemini key pools, Ollama URL,
embedding model, LangSmith tracing) works exactly as it does locally — no
code changes needed to go from dev to prod on that front. If ST2i
eventually provides paid API keys instead of free-tier ones, that's
purely an `.env` value swap, nothing in the code assumes free-tier.

---

## 5. Bring the stack up

```bash
git clone <repo-url> adequia && cd adequia
# create backend/.env and frontend/.env with real values (see section 4)
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose ps   # confirm everything is healthy/running
```

Migrations (`migrate` service) and the LangGraph checkpointer setup
(`checkpointer-setup` service) both run automatically as one-shot jobs
before `api`/`worker` start — no separate manual step needed, same as
local dev.

---

## 6. Backups — the one thing genuinely missing from local dev

Postgres is the single source of truth (candidates, TDRs, matches,
skill taxonomy, human review decisions) and currently has no backup
story beyond the Docker named volume itself. On a real server, add a
daily `pg_dump` cron job at minimum:

```bash
# /etc/cron.daily/adequia-pg-backup (example)
docker exec adequia-postgres-1 pg_dump -U postgres adequia | gzip > /var/backups/adequia/adequia-$(date +%F).sql.gz
find /var/backups/adequia -mtime +14 -delete   # keep 2 weeks
```

Redis doesn't need backup here — it only holds transient RQ job-queue
state, nothing that isn't safely re-derivable.

---

## 7. Log growth (only matters for a long-lived deployment)

Docker's default `json-file` log driver has no size cap out of the box.
Fine for a demo, not fine for a server that runs for months. Add to the
prod override if this deployment is meant to stay up long-term:

```yaml
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
```
(under each service in `docker-compose.prod.yml`, or as a global default
in `/etc/docker/daemon.json` on the host — either works, the daemon-level
one is less repetitive.)

---

## 8. Redeploying after a code change

```bash
git pull origin sprint-1   # or whatever the merged main branch ends up being
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```
Migrations run again automatically and are safe to re-run (Alembic only
applies what hasn't been applied yet).

---

## 9. Quick sanity checklist once it's live

- [ ] `curl -I https://<domain>/` returns 200 through the real proxy/TLS,
      not just on `localhost` from the server itself.
- [ ] `docker compose ps` — all services `Up`/`healthy`, none restarting
      in a loop (`docker compose logs -f <service>` if anything looks off).
- [ ] Upload one real CV + TDR through the live URL to confirm the whole
      pipeline works end-to-end on the new server, not just that
      containers started.
- [ ] `ollama list` on the host shows both `hermes3:3b` and
      `nomic-embed-text` — if either's missing, embeddings/extraction
      fallback will fail loudly (`EmbeddingBackendUnavailableError`) the
      first time free-tier keys get exhausted.
- [ ] Confirm the backup cron job actually ran once
      (`ls /var/backups/adequia/`) before you leave site.
