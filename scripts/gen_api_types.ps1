# Export backend OpenAPI and regenerate frontend TypeScript API types.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Push-Location (Join-Path $root "backend")
try { uv run python -m scripts.export_openapi; if ($LASTEXITCODE -ne 0) { throw "export_openapi failed" } } finally { Pop-Location }
Push-Location (Join-Path $root "frontend")
try { corepack pnpm@10.18.3 gen:api; if ($LASTEXITCODE -ne 0) { throw "gen:api failed" } } finally { Pop-Location }
