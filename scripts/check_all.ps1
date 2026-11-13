# Run all local checks (backend, API-type freshness, frontend). Stops on first failure.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

function Invoke-Step([string]$dir, [scriptblock]$cmd, [string]$name) {
    Push-Location $dir
    try {
        & $cmd
        if ($LASTEXITCODE -ne 0) { throw "FAILED: $name (exit $LASTEXITCODE)" }
    } finally { Pop-Location }
}

Write-Host "== backend =="
$be = Join-Path $root "backend"
Invoke-Step $be { uv run python -m ruff check . } "ruff"
Invoke-Step $be { uv run python -m mypy app } "mypy"
Invoke-Step $be { uv run python -m pytest -q } "pytest"
Invoke-Step $be { uv run python -m scripts.validate_catalog } "validate_catalog"

Write-Host "== API contract freshness =="
Invoke-Step $root { & (Join-Path $root "scripts/gen_api_types.ps1") } "gen_api_types"
Invoke-Step $root { git diff --exit-code -- backend/openapi.json frontend/src/lib/api/schema.d.ts } "api types current"

Write-Host "== frontend =="
$fe = Join-Path $root "frontend"
Invoke-Step $fe { corepack pnpm@10.18.3 lint } "lint"
Invoke-Step $fe { corepack pnpm@10.18.3 typecheck } "typecheck"
Invoke-Step $fe { corepack pnpm@10.18.3 build } "build"

Write-Host "All checks passed."
Write-Host "Hint: e2e is separate and slow: cd frontend; corepack pnpm@10.18.3 test:e2e (locally: set PW_CHANNEL=chrome)"
