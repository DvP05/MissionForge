# MISSIONFORGE frontend

Next.js 16 / React 19 / Tailwind / Recharts / Zustand UI for MISSIONFORGE. It renders results computed
by the Python backend and never calculates an authoritative number itself. Setup, the backend, and the
full check script are in the [root README](../README.md).

```bash
corepack pnpm@10.18.3 install
corepack pnpm@10.18.3 dev          # http://localhost:3000 (backend on http://127.0.0.1:8000)
corepack pnpm@10.18.3 lint
corepack pnpm@10.18.3 typecheck
corepack pnpm@10.18.3 build
corepack pnpm@10.18.3 test:e2e     # Playwright + axe; PW_CHANNEL=chrome uses an installed Chrome
```

API types in `src/lib/api/schema.d.ts` are generated from the backend's OpenAPI schema
(`bash ../scripts/gen_api_types.sh`); do not edit them by hand. Read `AGENTS.md` before changing
Next.js code: this Next.js version differs from older documentation.
