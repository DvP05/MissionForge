#!/usr/bin/env bash
# Run all local checks (backend, API-type freshness, frontend). Fails fast.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "== backend =="
cd "$ROOT/backend"
uv run python -m ruff check .
uv run python -m mypy app
uv run python -m pytest -q
uv run python -m scripts.validate_catalog

echo "== API contract freshness =="
cd "$ROOT"
bash scripts/gen_api_types.sh
git diff --exit-code -- backend/openapi.json frontend/src/lib/api/schema.d.ts

echo "== frontend =="
cd "$ROOT/frontend"
corepack pnpm@10.18.3 lint
corepack pnpm@10.18.3 typecheck
corepack pnpm@10.18.3 build

echo "All checks passed."
echo "Hint: e2e is separate and slow: cd frontend && corepack pnpm@10.18.3 test:e2e (locally: PW_CHANNEL=chrome)"
