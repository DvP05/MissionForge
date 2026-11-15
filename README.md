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

| Scenario | Mission | What it teaches | One way to make the starter design mission-ready |
|---|---|---|---|
| **Echoes of Origins** (`neo-rendezvous`) | Near-Earth asteroid rendezvous | Targets come from the JPL Small-Body Mission Design API (through the backend only); launch C3 vs spacecraft delta-v; link budget | Replace the low-gain radio with the medium-gain one |
| **Shadowline** (`lunar-polar-scout`) | Lunar polar orbiter | Power and thermal near permanently shadowed regions, contact windows, data return | High-gain radio plus a 250 kbit/s downlink rate, or observe less (duty × 0.6, at a science cost) |
| **Blue Sentinel** (`earth-observation`) | Earth observation | Data volume, downlink and storage trades | Lengthen ground-station passes to 90 min or more |

Each starter design has one deliberate weakness. These fixes were checked against the engine; other designs
work too.

## Player journey

The app is a mission console: a **station rail** on the left reaches every stage, and a **telemetry strip**
on top shows the active mission's target, design revision, analysed link margin and readiness (real values
only). Every mission page also shows the stage rail, the recommended next step, milestones and badges.

1. **Command centre** (`/`): continue a saved mission or start a scenario; load the saved demo mission.
2. **Mission briefing** (`/mission/<id>`): scenario, science objectives, measurement requirements,
   traceability, and (asteroid scenario) the target picker with a source badge.
3. **Science lab** (`/science/<id>`): objective → measurement → instrument → engineering consequence →
   expected return, with the serving instruments highlighted on the 3D spacecraft.
4. **Mission architect** (`/architect/<id>`):
   - **Spacecraft:** a 3D model built from the catalogue (placeholder geometry, not to scale; 2D fallback
     without WebGL), with exploded, technical and subsystem views.
   - **Changing parts:** explicit **Add / Replace / Remove** with confirmation (old vs new specs, or
     the measurements a removal would leave uncovered), and **Undo** as a new design revision.
   - **Impact report:** the engine's before/after values for each change.
   - **Readiness gates:** GO / WATCH / NO-GO groups of the engine's checks.
   - **Operations plan:** downlink rate (up to the radio's maximum), pass length and observation duty
     cycle.
   - **Live budget rail.**
   - **Launch:** blocked while a hard constraint fails. A WATCH still allows launch but keeps the design
     from "mission-ready".
5. **Trade study** (`/arena/<id>`): Pareto explorer, robustness lab (Monte Carlo) and side-by-side
   comparison of alternative designs.
6. **Readiness review** (`/readiness/<id>`):
   - a gate-by-gate audit with actual / limit / margin for every constraint;
   - **what blocks the mission-ready verdict**, with a link back to fix it;
   - flight authorisation (launch).
7. **Mission control** (`/control/<runId>`): deterministic seeded run, mission map, telemetry bus and
   history, operator decisions, onboard autonomy during communication blackouts, health-monitor residuals.
8. **Mission debrief** (`/review/<runId>`): outcome, objectives, score, science returned, margins, root
   causes, counterfactuals, design analyst, and the **Evidence Passport** export (re-importable JSON plus
   self-contained HTML).
9. **Blueprints hangar** (`/archive`): saved designs and flown runs in this browser.

**Mission-ready vs launchable:**
- the engine calls a design **mission-ready** only when every modelled constraint passes;
- a **FAIL** blocks a normal launch (an experimental, badged what-if is offered instead);
- a **WATCH** allows launch but not the mission-ready verdict.

The UI never shows "mission-ready" itself; it only reports the engine's verdict.

The interface follows the "Aerospace Mission Telemetry & Command System" design (graphite panels, machined
corners, Space Grotesk and JetBrains Mono, self-hosted). How the frontend was built, and which libraries
were used, is in [docs/frontend-design.md](docs/frontend-design.md).

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

Use **Load saved demo mission** on the command centre (`data/demo/demo-saved.json`, seed 42) for a
reliable judging run; it works offline.

A short live route:
1. Start **Echoes of Origins** and open the architect. The link-margin gate is NO-GO and launch is refused.
2. Replace the radio with the medium-gain link. The impact report shows link margin FAIL → PASS and the
   design becomes mission-ready.
3. Open the readiness review, then launch.
4. Make a decision in mission control.
5. Export the Evidence Passport from the debrief.

The rehearsal list is in [docs/release-checklist.md](docs/release-checklist.md).

## Checks

```bash
bash scripts/check_all.sh            # or scripts/check_all.ps1 on Windows
```

This runs ruff, mypy and pytest for the backend (1171 tests), the catalogue validator, an OpenAPI →
TypeScript freshness check, and eslint / tsc / `next build` for the frontend.

End-to-end tests are separate (148 Playwright tests, with axe at 1280 px and 375 px). They also check that
3D parts never overlap for any bus size, and that the hangar never loads the 3D engine:

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
frontend/           Next.js 16 / React 19 / Tailwind / Recharts / Zustand UI, React Three Fiber (3D),
                    anime.js + Motion (animation), Playwright e2e
  src/lib/spacecraft/  catalogue -> 3D mapping, gates, engineering status (presentation only)
  src/lib/progress/    stages, badges and challenges from real state
data/               catalogue, scenario templates and event sets, uncertainty profile, demo, JPL snapshot
docs/               release checklist, frontend design notes, build plan
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
