# MISSIONFORGE

> **Design it. Stress it. Fly it. Learn why it worked—or failed.**

MISSIONFORGE is an interactive, research-informed space mission design and operations game for the 2026 NASA Space Apps Challenge. Players translate a science question into measurable requirements, assemble a spacecraft, trade mass/power/propulsion/communications/cost, run a mission, respond to anomalies, and review the scientific return.

**Important:** MISSIONFORGE is an independent educational prototype. It is not a NASA product or flight-design tool. The app must label every result as source-backed, derived, gameplay estimate, or not modelled.

---

## 1. What makes MISSIONFORGE different

Most simple spacecraft games let players choose parts and then show a success score. MISSIONFORGE makes the causal chain visible:

```text
Science question
  → measurement requirement
    → instrument and observing plan
      → mass + power + pointing + data volume
        → propulsion + trajectory + launch feasibility
          → communications + operations plan
            → returned science and mission outcome
```

The core feature is a live **evidence-aware mission digital twin**. Change an instrument, antenna, battery, propulsion system, or operating plan and the connected budgets and traceability graph update. Then explore three defensible architectures on a Pareto frontier, test whether the design survives uncertainty, and watch the spacecraft adapt its science plan during a communication blackout. A mission can be affordable but scientifically weak, scientifically ambitious but underpowered, or nominally feasible but fragile. The simulator explains the causal chain behind every outcome.

### Product pillars

1. **Science-first engineering:** Every payload should trace to a science objective and measurement requirement.
2. **Real data, with honesty:** The asteroid mission path can use JPL Small-Body Mission Design data. Other scenario values are curated and labeled at their actual fidelity.
3. **Coupled systems:** Mass, delta-v, power, ADCS, data storage, communications, cost, and reliability are connected.
4. **Operations matter:** Players do not stop at “design complete”; they operate the mission and handle anomalies.
5. **Explainability:** Every warning and final score includes the underlying rule and assumptions.
6. **Repeatable science:** Same design + same engine/catalogue versions + same seed = same simulation result.
7. **Trade-offs, not a magic score:** Pareto exploration presents Lean, Science-max and Resilient designs without pretending one is universally best.
8. **Autonomy under uncertainty:** Science beliefs update from observations; onboard policies act during communication blackout.
9. **Auditable evidence:** The Mission Evidence Passport records sources, assumptions, versions, seeds and decisions.

---

## 2. Challenge alignment

The official challenge asks for an interactive game that lets participants design, manage, and simulate a complete space mission while balancing mission objectives, spacecraft design, science instruments, launch vehicles, budgets, power, mass, communications, and orbital constraints.

| Challenge requirement | MISSIONFORGE feature |
|---|---|
| Mission objectives | Brief builder and weighted science objectives |
| Spacecraft design | Configurable spacecraft subsystem catalogue |
| Scientific instruments | Payload selection linked to measurement requirements |
| Launch vehicles | Launch option and launch mass / energy checks |
| Budgets | Cost, mass, power/energy, propellant, and data budgets |
| Communications | RF link-budget proxy, contact windows, downlink backlog |
| Orbital constraints | JPL mission-design options for NEO scenario; explicit presets elsewhere |
| Mission management | Mission phases, telemetry, decision cards, anomaly handling |
| Evaluate success | Science return, system margins, risk, score, and post-mission autopsy |

---

## 3. Target experience

### Scenario 1 — NEO Rendezvous: “Echoes of Origins”

Design a robotic mission to investigate a near-Earth asteroid. Select the target from a JPL-derived list of accessible small bodies, compare departure windows and time-of-flight options, configure an orbiter/rendezvous spacecraft, choose instruments, and plan science/downlink operations.

This is the flagship demo because the data path can show an authentic connection to JPL's Small-Body Mission Design API. JPL data is fetched by the server adapter, cached, version-checked, and presented with source attribution. If the network is unavailable, a clearly labeled saved snapshot keeps the demo functioning.

### Scenario 2 — Lunar Polar Scout: “Shadowline”

Design a small lunar polar reconnaissance mission. Balance payload capability, power generation/storage, landing/scouting constraints, communications visibility, and mission duration. The first version uses a curated scenario preset; it does not claim high-fidelity lunar navigation or landing simulation.

### Scenario 3 — Earth Observation: “Blue Sentinel”

Design a low-Earth-orbit observation mission. Trade instrument resolution/data rate, revisit/coverage proxy, pointing, power, storage, and downlink capacity. The orbit is a transparent two-body educational preset.

---

## 4. Core gameplay loop

1. Choose a mission scenario and review the scientific challenge.
2. Define 2–4 science objectives.
3. Map each objective to measurable requirements.
4. Choose a destination / trajectory option.
5. Configure bus, launch, propulsion, power, ADCS, comms, C&DH, thermal and instruments.
6. Watch live mass, energy, delta-v, link, data, budget and science coverage.
7. Fix all hard constraints and accept documented risks.
8. Baseline the design and operations plan.
9. Run the mission through launch, commissioning, cruise, target operations, science and downlink.
10. Resolve anomalies with trade-offs.
11. Review returned science, realized failures, margins, score, source quality and counterfactuals.
12. Export a mission dossier and compare designs.

---

## 5. Technology stack

Use a **Python-first engineering architecture** with one Python/FastAPI modular-monolith backend and a separate Next.js presentation frontend. The main mission architecture, domain model, engineering engine, simulator, optimizer, uncertainty analysis, science autonomy, scheduler and data adapters must be implemented in Python. TypeScript is for UI and generated API clients only. Do not create a microservice fleet for a hackathon.

| Layer | Choice |
|---|---|
| UI | Next.js App Router + React + TypeScript |
| Styling | Tailwind CSS + shadcn/ui |
| 3D / scene | Three.js + React Three Fiber, lazy-loaded |
| Charts | Recharts |
| Client state | Zustand |
| Backend API validation | FastAPI + Pydantic v2 |
| Main domain / engineering logic | Pure Python under `backend/app/domain` |
| Tests | pytest + Playwright |
| Local saves | IndexedDB or localStorage with JSON export/import |
| External data | Server-only JPL adapter |
| Hosting | Next.js frontend host plus one Python/FastAPI backend host |
| Package managers | `uv` for Python backend; `pnpm` for frontend |

The versions should be pinned by the generated package manifest and lockfile. Do not let individual agents independently upgrade dependencies.

---

## 6. Repository layout

```text
missionforge/
├── README.md
├── architecture.md
├── module_breakdown.md
├── prod.md
├── research_basis.md
├── .env.example
├── data/
│   ├── catalog/
│   └── missions/
├── backend/
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── app/
│   │   ├── main.py
│   │   ├── api/routes/        # FastAPI endpoints
│   │   ├── schemas/           # Pydantic API/domain contracts
│   │   ├── services/          # application orchestration
│   │   ├── domain/            # authoritative Python mission architecture
│   │   │   ├── units/
│   │   │   ├── mission/
│   │   │   ├── catalog/
│   │   │   ├── analysis/
│   │   │   ├── simulation/
│   │   │   ├── optimization/
│   │   │   ├── uncertainty/
│   │   │   ├── science_belief/
│   │   │   ├── operations/
│   │   │   └── health_monitor/
│   │   ├── integrations/jpl/
│   │   └── infrastructure/
│   ├── tests/unit/
│   ├── tests/contract/
│   ├── tests/integration/
│   └── scripts/
├── frontend/
│   ├── package.json
│   ├── pnpm-lock.yaml
│   ├── next.config.ts
│   ├── tsconfig.json
│   ├── src/
│   │   ├── app/
│   │   ├── components/
│   │   ├── state/             # UI-only Zustand state
│   │   └── lib/               # generated OpenAPI types/API client
│   └── tests/e2e/
└── public/data/demo-jpl-snapshot.json
```

**Source-of-truth rule:** all canonical mission models and authoritative engineering logic live in `backend/app/` and are written in Python. FastAPI + Pydantic generate the API contract. Frontend TypeScript types are generated from OpenAPI and are not independently authored domain models. Read `architecture.md` for the full Python domain contracts, equations, service APIs and data policy; read `module_breakdown.md` for Python backend module ownership and parallel work assignments.

## 7. Prerequisites

- Python 3.12 or newer.
- `uv` for Python dependency and environment management.
- Node.js LTS compatible with the selected Next.js release.
- `pnpm` for frontend dependencies and scripts.
- Git.
- Modern Chromium/Firefox/Safari browser with WebGL for the full 3D scene. A 2D fallback must remain available.
- Internet access for live JPL lookups. The offline demo must work without it.

No external database, sign-in provider, paid API, or API key is required for the MVP.

## 8. Local setup

The frontend and Python backend run as two development processes. The authoritative mission calculations always execute in the Python backend.

```bash
# 1. Clone and enter the repo
git clone <YOUR_REPOSITORY_URL> missionforge
cd missionforge

# 2. Install and start the Python backend
cd backend
uv sync
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# 3. In a second terminal, install and start the frontend
cd ../frontend
pnpm install
cp ../.env.example .env.local
pnpm dev
```

Open `http://localhost:3000`. FastAPI docs are available at `http://127.0.0.1:8000/docs` during development.

### Expected backend commands

```bash
cd backend
uv run uvicorn app.main:app --reload
uv run pytest
uv run ruff check .
uv run mypy app
uv run python -m scripts.validate_catalog
```

### Expected frontend commands

```bash
cd frontend
pnpm dev
pnpm build
pnpm lint
pnpm typecheck
pnpm test:e2e
```

If a command has not yet been implemented, add it before asking another agent to rely on it.

## 9. Environment variables

`.env.example` should contain documented placeholders only:

```dotenv
# App metadata used in the JPL User-Agent. Set a monitored project contact.
APP_NAME=MISSIONFORGE
APP_VERSION=0.1.0
APP_CONTACT_EMAIL=team@example.com

# JPL SSD mission-design endpoint (server-side only)
JPL_MDESIGN_BASE_URL=https://ssd-api.jpl.nasa.gov/mdesign.api
JPL_REQUEST_TIMEOUT_MS=10000
JPL_CACHE_TTL_A_SECONDS=43200
JPL_CACHE_TTL_Q_SECONDS=86400
JPL_CACHE_TTL_M_SECONDS=21600

# Python domain model / service versions
MISSION_SCHEMA_VERSION=1.0
ENGINE_VERSION=0.1.0
CATALOG_VERSION=0.1.0

# Frontend -> Python API base URL (local default)
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

Do not add the JPL endpoint to client-side fetch code. The endpoint is a server adapter dependency.

---

## 10. Data and scientific honesty

Every engineering parameter or result must contain:

- value and unit;
- fidelity badge: `source-backed`, `derived`, `gameplay-estimate`, or `not-modelled`;
- source name and URL where available;
- source version / publication date / retrieval date;
- equation/model ID for derived values;
- assumptions and uncertainty range where meaningful.

**Do not invent technical values and present them as NASA specifications.** If a value is selected to make the tutorial playable, label it as an illustrative gameplay estimate.

### External data provider

The flagship NEO scenario uses the JPL Small-Body Mission Design API:

- Mode A: accessible-object screening under selected launch-year and optimality constraints.
- Mode Q: stored mission options for a selected small body.
- Mode M: mission option grid for a porkchop-style plot (stretch goal).
- Mode T: orbit-neighbour target search (deferred).

Important JPL fair-use requirements: server-side access only, one request at a time, cache/reuse results, identify the app in the User-Agent, back off on errors/rate limits, and validate the response `signature.version`. The browser must never directly embed the API.

---

## 11. Engineering model summary

The full implementation specification is in `architecture.md`. The minimum engine includes:

- Mass: dry mass + explicit propellant + separate margin; no double-counted structure.
- Propulsion: ideal rocket equation, with trajectory `C3`, `V-infinity`, and spacecraft maneuver delta-v kept distinct.
- Power: duty-cycle loads, peak power, solar generation, eclipse energy and battery state of charge.
- Communications: free-space path loss, EIRP, receiver noise, `C/N0`, `Eb/N0`, link margin and downlink capacity.
- Data: payload data generated, compression, downlinked bits and buffer capacity.
- Science: weighted objective coverage based on instrument compatibility, observation time and successfully returned data.
- Cost: transparent educational cost estimate, not official NASA lifecycle costing.
- Reliability: explicit failure modes, risk prioritization and seeded uncertainty.
- Simulation: mission-phase state machine with telemetry, events, player decisions and deterministic replay.

Hard constraints are separate from the weighted score. A mission can have an attractive score but still be infeasible; the interface must say so.

---

## 12. AI coding-agent operating instructions

These rules are mandatory when delegating to Codex, Claude Code, Cursor, or another coding agent.

### 12.1 Global agent contract

Paste this as the system/project instruction in each coding agent:

```text
You are implementing MISSIONFORGE, an educational mission design and operations simulator.
Read README.md, architecture.md, and prod.md before changing code.

Architecture rules:
1. Python 3.12+ is mandatory for the main architecture: canonical mission models and all engineering/domain logic live in `backend/app/`.
2. Use FastAPI + Pydantic v2 for API boundaries and contracts. Generate frontend TypeScript API types from OpenAPI.
3. Keep engineering calculations in pure Python functions under `backend/app/domain`; never put physics in React components or FastAPI route handlers.
4. The frontend is presentation-only and must not implement a competing TypeScript mission engine.
5. SI units are canonical internally. Use explicit conversion utilities.
6. All numeric values must carry unit, fidelity, provenance, and assumptions where applicable.
7. Keep JPL API access server-only. Never fetch JPL directly from the browser.
8. JPL calls must be serialized, cached, version-checked, identified with an app-specific User-Agent, and resilient to rate limits/outages.
9. Keep hard feasibility constraints separate from game score.
10. Simulation must be deterministic for a fixed mission, engine/catalogue version, and seed; use an explicitly seeded Python RNG.
11. Add pytest coverage for every Python domain behavior. Do not invent NASA specifications; use source-backed data or clearly label gameplay estimates.

Before coding, state the files you will touch and the tests you will add. Do not rewrite shared domain types without approval. Do not add dependencies unless necessary. After coding, report changed files, tests run, known limitations, and any assumptions.
```

### 12.2 Recommended agent split

| Agent | Owns | Must not edit |
|---|---|---|
| A — Python domain lead | `backend/app/domain/**`, backend unit tests | UI pages, JPL network adapter |
| B — UI lead | `frontend/src/app/**`, `frontend/src/components/**`, `frontend/src/state/**` | physics equations, canonical Pydantic models |
| C — Python data integration lead | `backend/app/integrations/jpl/**`, cache, FastAPI routes | UI state and simulation/domain logic |
| D — QA / integration lead | `backend/tests/**`, `frontend/tests/e2e/**`, scripts, fixtures, integration wiring | shared Pydantic models without agreement |
| Human integrator | shared schemas, package manifest, merges, design decisions | — |

For a two-person team, combine A+D and B+C. A single agent should own `MissionState`, `CatalogComponent`, `MissionAnalysis`, and API envelope types. Other agents import those contracts; they do not recreate similar types.

### 12.3 Task prompt template

```text
Task: <one measurable task>
Read: architecture.md sections <x,y>, prod.md requirement <ID>.
Allowed files: <explicit list>.
Do not edit: <protected files>.
Contract: <input and output types to use>.
Acceptance criteria:
- <observable behavior>
- <edge case>
- <test>
Constraints: keep domain calculations pure; preserve provenance; no unlabelled constants.
Return: summary, files changed, tests run, assumptions, open issues.
```

### 12.4 Agent task order

1. **Python foundation agent:** Pydantic models, unit utilities, catalogue validator, seed mission.
2. **Python engine agent:** mass/propulsion/power/data/comms/science analysis + pytest vectors.
3. **UI agent:** landing → brief → architect with seed mission; mock analysis initially.
4. **Integration agent:** connect UI to real analysis; implement stale-result protection.
5. **Python JPL agent:** FastAPI-backed adapter with fixture-driven parser; live mode A then Q; offline snapshot.
6. **Simulation agent:** seeded PRNG, phases, events, anomaly choices and report.
7. **Polish agent:** mission control visuals, review page, animations, responsive states.
8. **QA agent:** run clean install, unit, contracts, E2E and manual source audit.

Do not have several agents concurrently change the same shared contract or package manifest. Merge a vertical slice before starting the next one.

---

## 13. Development milestones

### Milestone 0 — Runnable skeleton

- [ ] Python FastAPI backend runs locally and exposes `/health` / OpenAPI.
- [ ] Next.js frontend runs locally and calls the Python API.
- [ ] Backend pytest/Ruff checks and frontend TypeScript/lint checks exist.
- [ ] Landing page and navigation exist.
- [ ] One valid seed mission loads.

### Milestone 1 — Trustworthy engine

- [ ] Unit conversion utilities.
- [ ] Mass and propulsion models.
- [ ] Power, communications and data models.
- [ ] Science coverage model.
- [ ] Constraint orchestration and explainable warnings.
- [ ] Engine tests pass.

### Milestone 2 — Complete design loop

- [ ] Objective / measurement editor.
- [ ] Catalogue selection.
- [ ] Live budget panels.
- [ ] Hard feasibility status.
- [ ] Compare two architectures.

### Milestone 3 — Authentic asteroid data

- [ ] JPL API adapter + fixture.
- [ ] Serialized queue, cache, User-Agent, timeout/backoff.
- [ ] Mode A and Q work.
- [ ] Source attribution and version mismatch fallback.
- [ ] Offline demo snapshot.

### Milestone 4 — Mission operations

- [ ] Six or more mission phases.
- [ ] Telemetry updates at phase checkpoints.
- [ ] At least two meaningful anomaly decision branches.
- [ ] Deterministic replay.
- [ ] Final mission report and counterfactual.

### Milestone 5 — Demo polish

- [ ] Three scenario templates.
- [ ] 3D / 2D fallback.
- [ ] Responsive layout and accessibility pass.
- [ ] Dossier export.
- [ ] Full clean-install demo rehearsal.

---

## 14. Run the demo in a reliable order

Recommended 4–6 minute live demonstration:

1. Start “Echoes of Origins” and show a real JPL-derived target candidate with source badge.
2. Choose a science objective and reveal the measurement requirements.
3. Add a high-data-rate instrument; show mass, power, data backlog and cost change together.
4. Add a better antenna or revise the observing schedule; show the downlink constraint recover.
5. Run validation and explain a remaining warning.
6. Launch the mission simulation; show commissioning and cruise telemetry.
7. Trigger a seeded anomaly caused by the selected design or operating plan; choose a recovery action.
8. Finish at the mission review: science returned, data lost, margins, uncertainty estimate, score breakdown, and “what one design change would have prevented this?”
9. Export the mission dossier.

Always have the saved, seeded demo mission loaded locally. Do not rely on a live external API request completing during the judging window.

---

## 15. Quality gates before submission

- [ ] Clean `uv sync` in `backend/` and `pnpm install` in `frontend/` succeed from a fresh clone.
- [ ] `pnpm lint`, `pnpm typecheck`, `pnpm test`, `pnpm build` pass.
- [ ] Core Playwright flow passes.
- [ ] No browser-side JPL requests.
- [ ] JPL version check, serialization, cache and fallback verified.
- [ ] No unlabelled numerical assumptions.
- [ ] No failed constraint hidden behind the overall score.
- [ ] Same seeded mission produces same result.
- [ ] Works without JPL network access.
- [ ] Mobile layout and WebGL fallback verified.
- [ ] Credits and non-endorsement statement visible.

---

## 16. Sources and further reading

- NASA Space Apps 2026 challenge listing: https://www.spaceappschallenge.org/2026/challenges/space-mission-design-game/
- NASA Systems Engineering Handbook: https://www.nasa.gov/reference/systems-engineering-handbook/
- NASA Small Spacecraft State-of-the-Art (2026): https://www.nasa.gov/smallsat-institute/sst-soa/
- NASA Model-Based Science Mission Formulation paper: https://ntrs.nasa.gov/citations/20220019154
- JPL Small-Body Mission Design API: https://ssd-api.jpl.nasa.gov/doc/mdesign.html
- JPL SSD API fair-use policy: https://ssd-api.jpl.nasa.gov/doc/
- NASA VISITOR: https://software.nasa.gov/software/LAR-18538-1
- DSN Telecommunications Link Design Handbook: https://deepspace.jpl.nasa.gov/dsndocs/810-005/
- Satellite multidisciplinary design optimization, DOI: https://doi.org/10.1177/0954410016665412
- Small-satellite design and operation optimization, DOI: https://doi.org/10.2514/1.A32751
- Mission design under uncertainty, DOI: https://doi.org/10.1016/j.actaastro.2009.09.005
- Engineering serious-game decision-making systematic review, DOI: https://doi.org/10.1080/03043797.2026.2672137
- Gamification in engineering education, DOI: https://doi.org/10.1016/j.heliyon.2020.e04972

For the detailed bibliography and how each source influences the architecture, see section 18 of `architecture.md`.


## 17. Research upgrades that make MISSIONFORGE distinctive

The architecture is grounded in published methods, but the hackathon product uses deliberately simplified implementations that are transparent and testable.

| Research-backed idea | What players experience | Hackathon implementation |
|---|---|---|
| Model-based system architecture + traceability | A live graph from science question to instrument to mission result | Typed nodes/edges; STM/MTM projections; causal impact report |
| Multi-objective architecture optimization | Three viable designs and a Pareto frontier, not a single score | Seeded candidate generation, pure mission evaluation and non-dominated sorting |
| Robust mission design | “How often does this mission remain feasible?” | Seeded Monte Carlo, metric quantiles and Wilson interval |
| Science belief-state planning | A new observation changes what the spacecraft believes | Bayesian updates across a small synthetic hypothesis set |
| Deep-space autonomy | The spacecraft chooses its next science action during blackout | Three explainable onboard policies with hard resource checks |
| Integrated science/downlink scheduling | Valuable images compete with power, memory and contact windows | One-spacecraft greedy data-cycle scheduler |
| Telemetry anomaly detection | A sensor drift is detected and linked to a failure event | EWMA residual, thresholds and persistence rule |

### The signature feature: “Discover, then adapt”

The flagship asteroid scenario should be scripted around a science discovery. The player begins with competing hypotheses about the target (all clearly marked as synthetic game scenario assumptions). An instrument observation updates the probability distribution. Earth is temporarily out of contact. The onboard policy then chooses the next observation using expected science value, information gain, energy, pointing and data-storage limits. The mission review shows whether the new evidence changed the science conclusion and what the spacecraft sacrificed to obtain it.

This combines the most interesting ideas from recent science autonomy and belief-state planning research in a way that can be built without pretending to solve a full POMDP.

### The second signature feature: “There is no single best spacecraft”

Mission Design Arena shows the Lean, Science-max and Resilient architecture candidates, plus a Pareto scatter plot. A player can inspect why the cheaper spacecraft returns less science or why the robust spacecraft accepts more mass/cost to improve chance of success. This directly demonstrates multidisciplinary design optimization.

### The third signature feature: “Show me the evidence”

Every value and recommendation should expose its source, equation, assumption, fidelity tier and model version. The exported Mission Evidence Passport acts as a compact engineering review package. It should be possible for a technically literate judge to inspect a mission and understand where every major number came from.

---

## 18. Expanded repository layout

```text
backend/app/domain/
  architecture_graph/      # causality graph, impact trace and STM/MTM views
  optimization/            # candidate generation, dominance, Pareto frontier
  uncertainty/             # seeded samplers, Monte Carlo, confidence intervals
  science_belief/           # Bayesian update, entropy, expected information gain
  operations/               # autonomy policies, observation/downlink data cycles
  health_monitor/           # telemetry residuals, EWMA and anomaly rules
  analyst/                  # deterministic counterfactual recommendations
  dossier/                  # run manifest, evidence passport exporter
```

These modules are pure Python. They do not import React, Next.js, browser APIs, LLM clients, FastAPI route objects or network clients. The same logic must be testable with pytest without starting the web server. The frontend only consumes API results and generated TypeScript contracts.

---

## 19. Recommended AI-agent task sequence (expanded)

Do not start all agents simultaneously. First freeze `MissionState`, `MissionAnalysis`, unit contracts and catalogue schemas. Then give each agent one isolated module.

| Sequence | Agent task | Acceptance gate |
|---|---|---|
| 1 | Architecture graph + causal impact | Removing an instrument reveals the affected requirement and downstream budget changes |
| 2 | Pareto candidate explorer | 100+ deterministic candidates, valid non-dominated set, three explainable archetypes |
| 3 | Robustness lab | 100–250 seeded samples, probability + interval + p10/median/p90 |
| 4 | Science belief tracker | Posterior sums to 1; observation shifts beliefs in expected direction |
| 5 | Blackout autonomy | Ground commands blocked; selected onboard action explains its utility and resource cost |
| 6 | Observation/downlink scheduler | No unacknowledged buffer overflow; contact capacity and deadlines enforced |
| 7 | Telemetry health monitor | EWMA and persistence trigger a deterministic fault event with evidence |
| 8 | Mission Evidence Passport | Export records sources, limitations, seeds, versions, schedule and decisions |

### Global coding-agent rule additions

```text
11. Do not claim to implement a full paper method when the task specifies a
    simplified educational analogue. Preserve the method/fidelity disclaimer.
12. Never put LLM calls in the engineering, scoring, optimization, autonomy,
    anomaly detection or simulation critical path.
13. Keep all stochastic algorithms seeded and deterministic.
14. Preserve hard feasibility gates separately from Pareto objectives and score.
15. Do not use eval() or arbitrary dynamic property paths for uncertain inputs.
16. Every research-inspired feature must have known-answer tests and a source
    note in research_basis.md.
```

For detailed prompts and contracts, use sections 20–22 of `architecture.md`.

---

## 20. Updated five-to-six-minute demonstration

1. **Mission question:** open the asteroid scenario and show its science requirement.
2. **Causal architecture:** remove an instrument; show requirement coverage, power, data and returned science change.
3. **Trade-space:** open Pareto view; compare Lean, Science-max and Resilient designs.
4. **Robustness:** show the fraction of seeded scenarios that remain feasible and the uncertainty interval.
5. **Discovery:** run an observation and show the science belief update.
6. **Autonomy:** trigger a communication blackout; onboard policy picks a follow-up observation and schedule shows the power/data trade.
7. **Evidence:** open the mission autopsy and export the Mission Evidence Passport.

Do not demo every subsystem. Tell this one story clearly. Keep a saved, seeded run ready, because live JPL availability must not be a judging dependency.

---

## 21. Updated research library

The key additional literature and its implementation limits are summarized in `research_basis.md`. Particularly important additions:

- Guirguis et al. (2026), *POMDPs for Autonomous Science Exploration*, arXiv:2608.03155 — science-hypothesis beliefs and adaptive replanning.
- Kim et al. (2025), *Adaptive Science Operations in Deep Space Missions Using Offline Belief State Planning*, arXiv:2510.08812 — resource-aware onboard instrument sequencing.
- Babapour & Taheri (2026), *Robust Spacecraft Low-Thrust Trajectory Design*, arXiv:2601.17629 — chance constraints and mass-aware uncertainty.
- Iijima et al. (2026), *Global Optimization Framework for Automated Low-Thrust Gravity-Assist Trajectory Design*, arXiv:2609.09515 — broad search, pruning and local optimization.
- Bussemaker & Firchau (2025), *System architecture optimization: an example application to space mission planning* — Pareto exploration for system mass and scientific value.
- Levinson et al. (IJCAI 2025), *Optimal Planning to Coordinate Science Data Collection and Downlink...* — integrated observation and downlink planning.
- NASA, *State-of-the-Art of Small Spacecraft Technology*, 2026 edition — refreshed subsystem technology and technology-readiness context.
- Goetze et al. (2025 conference; 2026 arXiv), *Deep Learning-Based Anomaly Detection in Spacecraft Telemetry on Edge Devices* — constrained telemetry anomaly detection; MISSIONFORGE uses a transparent EWMA baseline, not the paper's neural model.

