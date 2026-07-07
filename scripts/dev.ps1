# One-command local dev startup: bootstraps env files, then runs the full
# stack (api, worker, web, postgres, redis) via Docker Compose. Migrations
# run automatically as the `migrate` service before api/worker start.
#
# Ollama is intentionally NOT started here -- it's a separate local app,
# not a container in this compose file (see OLLAMA_BASE_URL's
# host.docker.internal comment in docker-compose.yml). Pull models once
# per docs/11-sprint-1-dev-guide.md and leave it running in the background;
# this script only owns what's actually defined as a service here.

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot

function Copy-EnvIfMissing($dir) {
    $envPath = Join-Path $repoRoot "$dir/.env"
    $examplePath = Join-Path $repoRoot "$dir/.env.example"
    if (-not (Test-Path $envPath)) {
        Copy-Item $examplePath $envPath
        Write-Host "Created $dir/.env from $dir/.env.example -- fill in real API keys before relying on Groq/Gemini." -ForegroundColor Yellow
    }
}

Copy-EnvIfMissing "backend"
Copy-EnvIfMissing "frontend"

Set-Location $repoRoot
docker compose up --build
