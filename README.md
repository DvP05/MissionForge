# MISSIONFORGE

> **Design it. Stress it. Fly it. Learn why it worked — or failed.**

MISSIONFORGE is an interactive, research-informed space mission design and operations game built for the
2026 NASA Space Apps Challenge. You turn a science question into measurable requirements, assemble a
spacecraft, trade mass / power / propulsion / communications / cost, fly the mission through seeded
anomalies, and review what science came back and why.

**MISSIONFORGE is an independent educational prototype. It is not a NASA or JPL product, is not endorsed
by either, and is not a flight-design tool.** Every number is labelled as source-backed, derived, gameplay
estimate, or not modelled. See [LICENSE-NOTICE.md](LICENSE-NOTICE.md).

## Scenarios

| Scenario | Mission | What it teaches |
|---|---|---|
| **Echoes of Origins** (`neo-rendezvous`) | Near-Earth asteroid rendezvous | Targets come from the JPL Small-Body Mission Design API (through the backend only); launch C3 vs spacecraft delta-v |
| **Shadowline** (`lunar-polar-scout`) | Lunar polar orbiter | Power and thermal in permanently shadowed regions, contact windows |
| **Blue Sentinel** (`earth-observation`) | Earth observation | Data volume, downlink and storage trades |

## Player journey

1. **Mission hangar** (`/`): continue a saved mission or start a scenario.
2. **Mission brief** (`/mission/<id>`): science objectives, measurement requirements, and (asteroid
   scenario) the target picker with a source badge.
3. **Science lab** (`/science/<id>`): objective → measurement → instrument → engineering consequence →
   expected return, with the serving instruments highlighted on the spacecraft.
4. **Architect** (`/architect/<id>`): a 3D spacecraft built from the catalogue (placeholder geometry, not
   to scale). Install, replace and remove parts; the inspector, live engineering dashboard, budgets and
   constraints all show the backend analysis of the current design revision. Launch is blocked while a hard
   constraint fails.
5. **Trade study** (`/arena/<id>`): Pareto explorer, robustness lab (Monte Carlo), observation schedule.
6. **Mission control** (`/control/<runId>`): deterministic seeded run, telemetry, 2D mission map,
   operator decisions, onboard autonomy during communication blackouts, health-monitor residuals.
7. **Review** (`/review/<runId>`): root causes, counterfactuals, design analyst, and the
   **Evidence Passport** export (re-importable JSON plus self-contained HTML).
8. **Archive** (`/archive`): saved designs and flown runs in this browser.

How the frontend was rebuilt, and which libraries were used, is described in
[docs/frontend-design.md](docs/frontend-design.md).

All calculations run in the Python backend; the frontend never computes an authoritative result and never
calls JPL directly.

## Quick start

Prerequisites: Python 3.12+, [uv](https://docs.astral.sh/uv/), Node.js 24 LTS with corepack (pnpm 10.18.3
is pinned in `frontend/package.json`), Git. No database, sign-in, paid API or API key is needed.

```bash
# backend (terminal 1)
cd backend
uv sync
uv run python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

```bash
# frontend (terminal 2)
cd frontend
corepack pnpm@10.18.3 install
corepack pnpm@10.18.3 dev
```

Open http://localhost:3000. API docs are at http://127.0.0.1:8000/docs.

Optional: copy `.env.example` to `.env` at the repo root (backend) and `frontend/.env.local`
(`NEXT_PUBLIC_API_BASE_URL`). The defaults work without either.

### Offline by default

The app needs no network. Live JPL access is opt-in: it needs `JPL_LIVE_ENABLED=1` **and** a real
`APP_CONTACT_EMAIL` (sent in the User-Agent, as JPL asks). Otherwise the bundled snapshot
`data/jpl/demo-snapshot.json` is served and labelled. `JPL_FORCE_OFFLINE=1` always wins.

The bundled snapshot is **synthetic and labelled "not JPL data"** until someone captures a real one:

```bash
cd backend
uv run python -m scripts.capture_demo_data --contact you@your-domain --dry-run   # check only
uv run python -m scripts.capture_demo_data --contact you@your-domain             # write the snapshot
```

The script sends requests one at a time and validates every response before writing anything.

## Demo

Use **Load saved demo mission** on the home page (`data/demo/demo-saved.json`, seed 42) for a
reliable judging run; it works offline. The rehearsal list is in
[docs/release-checklist.md](docs/release-checklist.md).

## Checks

```bash
bash scripts/check_all.sh            # or scripts/check_all.ps1 on Windows
```

This runs ruff, mypy and pytest for the backend, the catalogue validator, an OpenAPI → TypeScript freshness
check, and eslint / tsc / `next build` for the frontend. End-to-end tests (Playwright + axe, 1280 px and
375 px) are separate:

```bash
cd frontend
corepack pnpm@10.18.3 test:e2e       # add PW_CHANNEL=chrome to use an installed Chrome
```

Useful backend scripts: `uv run python -m scripts.validate_catalog`, `uv run python -m
scripts.make_demo_package` (regenerate the demo package), `uv run python -m scripts.export_openapi`.
After changing an API schema, regenerate the frontend types with `bash scripts/gen_api_types.sh`.

## Repository layout

```text
backend/            FastAPI + Pydantic v2 service (all domain calculations)
  app/domain/       pure engine: analysis, simulation, operations, health monitor, optimisation, ...
  app/services/     orchestration over the domain layer
  app/api/routes/   HTTP routes (/api/...)
  app/integrations/ JPL Mission Design adapter (server-side only)
  app/schemas/      frozen API contracts (see CONTRACTS.md)
  scripts/          catalogue validator, demo package, JPL capture, OpenAPI export
  tests/            unit, integration, contract snapshot and golden tests
frontend/           Next.js 16 / React 19 / Tailwind / Recharts / Zustand / React Three Fiber UI, Playwright e2e
data/               catalogue, scenario templates and event sets, uncertainty profile, demo, JPL snapshot
docs/               release checklist and build plan
src-files/          product, architecture and research specifications
scripts/            check_all and API type generation
```

## Scientific honesty

- Catalogue components are illustrative archetypes (fidelity `gameplay-estimate`), not real products,
  pending a source audit. See [data/catalog/README.md](data/catalog/README.md).
- C3 is launch energy from the rocket; it is never added to spacecraft delta-v.
- Seeded runs are deterministic: the same mission and seed reproduce the same run, and the Evidence
  Passport re-checks the replay on the server before claiming it.
- No large language model computes any number.

Specifications: [src-files/README.md](src-files/README.md), [architecture](src-files/architecture.md),
[product requirements](src-files/prod.md), [research basis](src-files/research_basis.md).

## License

Code is MIT licensed ([LICENSE](LICENSE)). Attribution and non-endorsement:
[LICENSE-NOTICE.md](LICENSE-NOTICE.md).
