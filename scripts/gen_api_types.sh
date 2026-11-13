#!/usr/bin/env bash
# Export backend OpenAPI and regenerate frontend TypeScript API types.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
(cd "$ROOT/backend" && uv run python -m scripts.export_openapi)
(cd "$ROOT/frontend" && corepack pnpm@10.18.3 gen:api)
