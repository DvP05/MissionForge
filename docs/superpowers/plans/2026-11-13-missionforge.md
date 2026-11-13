# MISSIONFORGE Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build MISSIONFORGE, an evidence-aware educational space-mission design and operations game (design → analyse → simulate → review → export) for NASA Space Apps 2026.

**Architecture:** One Python 3.12 / FastAPI / Pydantic v2 modular-monolith backend owns every authoritative model and calculation (pure functions under `backend/app/domain`). A Next.js + TypeScript frontend is presentation-only and consumes TypeScript types generated from the backend's OpenAPI. JPL data is fetched server-side only, serialized, cached, version-checked, with a bundled offline snapshot.

**Tech Stack:** Python 3.12, `uv`, FastAPI, Pydantic v2, httpx, pytest, ruff, mypy · Next.js (App Router), React, TypeScript, Tailwind, shadcn/ui, Zustand, Recharts, Three.js/R3F (lazy), `pnpm`, Playwright, `openapi-typescript`.

**Spec:** `src-files/README.md`, `src-files/architecture.md` (technical authority), `src-files/prod.md` (acceptance criteria AC-01…AC-23), `src-files/module_breakdown.md` (M01–M19, gates G0–G6), `src-files/research_basis.md` (claims policy).

---

## Global Constraints

Copied from the spec; every task includes these implicitly.

- Python ≥ 3.12 owns the canonical `MissionState`, catalogue, analysis, simulation, optimisation, uncertainty, belief/autonomy, scheduling, health monitor, dossier and JPL adapter. TypeScript never re-implements physics, scoring, simulation, optimisation, uncertainty, autonomy or scheduling.
- `backend/app/domain/**` is pure: no FastAPI objects, no HTTP/DB clients, no wall-clock reads, no env vars, no unseeded randomness, no LLM calls, no `eval()` / dynamic attribute paths (uncertain-parameter paths come from an allow-list).
- SI units internally (kg, m, s, W, J, bit/s, Hz, K, Pa, rad); percentages are fractions 0..1 internally; conversions only in `domain/units`.
- Every numeric value/result carries `value`, `unit`, `provenance` (fidelity ∈ `source-backed | derived | gameplay-estimate | not-modelled`, source name/URL/version/dates, assumptions), model ID where derived, uncertainty where meaningful.
- Hard feasibility constraints are separate from the weighted score; a failed hard constraint can never yield "mission-ready".
- Reproducible: same `MissionState` + `ENGINE_VERSION` + `CATALOG_VERSION` + scenario event-set ID + seed ⇒ byte-identical serialized result. Randomness is an explicitly passed seeded `random.Random`.
- Rocket equation `ΔV = Isp·g0·ln(m0/mf)`, `g0 = 9.80665 m/s²`. C3 / V∞ / JPL `dv_tot` are never added to spacecraft ΔV. W ≠ Wh/J. Generated data ≠ downlinked data. No double-counted structure mass.
- Link budget constants: `kB = 1.380649e-23 J/K`, `c = 299792458 m/s`.
- Wilson 95 %: `z = 1.96`, `denom = 1+z²/n`, `center = (p+z²/2n)/denom`, `half = z·sqrt(p(1−p)/n + z²/4n²)/denom`, clamp to [0,1].
- JPL: server-only; concurrency 1; app-specific User-Agent (name, version, contact); 10 s timeout; capped exponential backoff on 429/5xx/timeouts only; validate `signature.version`; cache TTL A 12 h (43200 s), Q 24 h (86400 s), M 6 h (21600 s); unknown version ⇒ stale cache or demo snapshot with visible status; never expose raw payloads or a URL proxy.
- No invented NASA specs/vendors; unsourced values are `gameplay-estimate`; illustrative archetypes are flagged `is_illustrative`. No NASA logo/seal; visible "independent educational prototype, not endorsed by NASA/JPL" statement.
- Research-inspired features keep their fidelity disclaimer (no claims of NSGA-II toolchain, covariance steering, full POMDP, MILP optimality, neural anomaly detection).
- Performance: `analyze_mission` p95 < 100 ms; 3-design trade study < 300 ms; one simulation < 1 s; 250 candidates < 3 s; 250 robustness samples < 2 s; belief update < 1 ms; 50 opps/10 contacts schedule < 100 ms.
- ≥ 90 % line coverage on mass, propulsion, power, comms, data, scoring modules.
- Dependency/lockfile/manifest changes only in Task 0.x and by explicit request thereafter.
- Priority cut order if time collapses: 3D → extra scenarios → large catalogue → Mode M → PDF → advanced optimiser → ML anomaly → trajectory propagation → LLM. Never cut: shared types, unit correctness, fidelity labels, seed reproducibility, hard constraints, offline fallback, full journey.

## Review Focus

Inputs/conditions the spec implies but no single task's happy-path tests cover; each is pinned by a test in the owning task.

1. **Zero / empty inputs** (no instruments, no objectives, 0 downlink contacts, 0 feasible robustness samples) → structured result or constraint, never `NaN`/`Infinity`/crash. *(Tasks 2.2, 2.5, 6.3, 6.6)*
2. **Stale async results** — analysis for revision n arriving after n+1 must not overwrite state; rapid edits must not flicker. *(Task 3.4)*
3. **JPL misbehaviour** — 429 with `Retry-After`, timeout, unknown `signature.version`, malformed/short `records` rows, concurrent browser requests. *(Task 5.2)*
4. **Corrupt / hostile imports** — invalid JSON, wrong schema version, `NaN` literals, oversized files, HTML in titles, quota-exceeded storage. *(Tasks 4.5, 3.1)*
5. **Version mismatch on replay** — imported run with different engine/catalogue version must say "not identical replay", never claim exactness. *(Task 4.5)*

---

## Repository File Structure (target)

```text
missionforge/
├── .env.example  .gitignore  README.md  LICENSE-NOTICE.md (attribution + non-endorsement)
├── .github/workflows/ci.yml
├── scripts/                         # repo-level: check_all.sh/.ps1, gen_api_types
├── data/
│   ├── catalog/{launch,bus,propulsion,power,adcs,communications,thermal,cdh,instrument,ground}.json
│   ├── catalog/catalog_manifest.json            # CATALOG_VERSION, source list
│   ├── missions/{neo-rendezvous,lunar-polar-scout,earth-observation}.json
│   ├── scenarios/{neo-rendezvous}.events.json   # scenario event set + hypotheses + likelihoods
│   └── uncertainty/default_profile.json
├── public/data/demo-jpl-snapshot.json
├── backend/
│   ├── pyproject.toml  uv.lock
│   ├── app/
│   │   ├── main.py  config.py
│   │   ├── schemas/   units.py mission.py catalog.py analysis.py simulation.py trajectory.py
│   │   │              optimization.py uncertainty.py science_belief.py operations.py evidence.py api.py
│   │   ├── domain/
│   │   │   ├── units/{conversions,guards,constants}.py
│   │   │   ├── mission/{defaults,migrations,validation}.py
│   │   │   ├── catalog/{loader,resolver,compat}.py
│   │   │   ├── analysis/{mass,propulsion,power,data,comms,thermal,orbital,cost,reliability,science,constraints,score,drivers,orchestrator}.py
│   │   │   ├── architecture_graph/{build_architecture_graph,trace_impact,build_traceability_matrices}.py
│   │   │   ├── optimization/{generate_candidates,dominates,pareto_front,select_archetypes}.py
│   │   │   ├── uncertainty/{samplers,paths,wilson_interval,run_robustness}.py
│   │   │   ├── science_belief/{bayesian_update,entropy,expected_information_gain}.py
│   │   │   ├── operations/{score_actions,plan_autonomy,schedule_data_cycles}.py
│   │   │   ├── simulation/{prng,phases,events,telemetry,anomalies,decisions,runner,report}.py
│   │   │   ├── health_monitor/{ewma,detect_anomalies}.py
│   │   │   ├── analyst/{recommend_mutations,explain_constraint}.py
│   │   │   └── dossier/{build_run_manifest,export_mission_dossier}.py
│   │   ├── services/  api/{deps.py,routes/{health,catalog,templates,missions,space_data}.py}
│   │   ├── integrations/jpl/{client,models,normalize,repository,snapshot}.py
│   │   └── infrastructure/{cache/ttl_cache.py,queue/serial_queue.py}
│   ├── scripts/{validate_catalog,capture_demo_data,export_openapi}.py
│   └── tests/{unit,contract,integration,golden}/
└── frontend/
    ├── package.json pnpm-lock.yaml next.config.ts tsconfig.json playwright.config.ts
    ├── src/app/{page.tsx, mission/[missionId], architect/[missionId], arena/[missionId], control/[runId], review/[runId], about}
    ├── src/components/{shell,mission-brief,science-traceability,architect,budgets,arena,robustness,science-evidence,mission-control,schedule,review,scene,common}
    ├── src/state/{mission-store.ts,selectors.ts}   # UI-only
    ├── src/lib/{api/schema.d.ts (generated), api-client.ts, persistence/, format.ts}
    └── tests/e2e/
```

Implement only what the current vertical slice needs; create files when their task starts.

## Execution Phases & Gates

| Phase | Tasks | Gate (exit condition) |
|---|---|---|
| 0 Skeleton | 0.1–0.3 | **G0**: both apps boot; `/health`; CI scripts exist |
| 1 Contracts + data | 1.1–1.5 | **G1**: default NEO `MissionState` validates; catalogue validator green |
| 2 Engine | 2.1–2.8 | **G2** (with 3.x stub): edit → ≥2 coupled metrics change; explained warning |
| 3 API + Architect UI | 3.1–3.5 | Live budgets in browser, stale-response safe |
| 4 Simulation, Control, Review, Persistence | 4.1–4.6 | **G3**: full vertical slice + replay + reload |
| 5 JPL data | 5.1–5.3 | **G5**: live/cached/demo status; browser never calls JPL |
| 6 Differentiators | 6.1–6.9 | **G4**: ≥1 integrated (target: graph, Pareto, robustness, belief+autonomy, scheduler, health) |
| 7 Polish + release | 7.1–7.5 | **G6**: offline demo, exports, e2e, clean install |

Parallelism (after G1): {2.x engine, 3.x UI on mock fixtures, 5.x JPL, 4.5 persistence scaffold} are independent; {6.1,6.2,6.3} after 2.8; {6.4–6.6} after contracts frozen in Task 6.4; 6.7 after 4.1. One writer per file; contracts changed only via Task 1.x owner.

---

# Phase 0 — Runnable Skeleton (M01 scaffold, M19 start)

### Task 0.1: Backend scaffold

**Files:**
- Create: `backend/pyproject.toml`, `backend/app/main.py`, `backend/app/config.py`, `backend/app/api/routes/health.py`, `backend/app/schemas/api.py`, `backend/tests/integration/test_health.py`, `.env.example`, `.gitignore`

**Interfaces:**
- Produces: `app.main:app` (FastAPI); `Settings` (pydantic-settings) with `app_name, app_version, app_contact_email, jpl_mdesign_base_url, jpl_request_timeout_ms, jpl_cache_ttl_{a,q,m}_seconds, mission_schema_version, engine_version, catalog_version, cors_origins`; `ApiResult[T]`, `ApiMeta`, `ApiError`, `ContractModel` (camelCase alias, `populate_by_name`, `extra="forbid"`), `to_camel`.

- [ ] **Step 1: Write failing test** `test_health_returns_versions`: `GET /api/health` → 200, `ok is True`, `data.engineVersion == "0.1.0"`, `data.catalogVersion == "0.1.0"`, `data.jplAdapter.status in {"live","cached","demo","unknown"}`, `meta.requestId` non-empty, no env var names/values in body.
- [ ] **Step 2: Run** `cd backend && uv run pytest tests/integration/test_health.py -v` → FAIL (no app).
- [ ] **Step 3: Implement** `pyproject.toml` (deps: fastapi, uvicorn[standard], pydantic>=2, pydantic-settings, httpx; dev: pytest, pytest-asyncio, pytest-cov, ruff, mypy, respx; `[tool.ruff]`, `[tool.mypy] strict = true` for `app/domain`, `[tool.pytest.ini_options] asyncio_mode="auto"`), the app factory with CORS limited to `NEXT_PUBLIC` origin (`http://localhost:3000`), request-ID middleware (uuid4 → `meta.request_id`), global exception handler mapping to `ApiError(code="INTERNAL_ERROR")`, and `.env.example` exactly as README §9.
- [ ] **Step 4: Run** `uv sync && uv run pytest tests/integration/test_health.py -v` → PASS; `uv run ruff check . && uv run mypy app` clean.
- [ ] **Step 5: Commit** `feat(backend): FastAPI skeleton, settings, health route, API envelope`

### Task 0.2: Frontend scaffold + generated API client

**Files:**
- Create: `frontend/` (Next.js App Router TS, Tailwind, shadcn/ui init, Zustand, Recharts, Playwright), `frontend/src/app/{layout,page}.tsx`, `frontend/src/components/shell/{AppShell,Disclaimer}.tsx`, `frontend/src/lib/api-client.ts`, `backend/scripts/export_openapi.py`, `scripts/gen_api_types.{sh,ps1}`, `frontend/tests/e2e/smoke.spec.ts`
- Modify: `frontend/package.json` scripts: `dev, build, lint, typecheck, test:e2e, gen:api`

**Interfaces:**
- Produces: `apiGet<T>(path)`, `apiPost<T,B>(path, body)` returning `ApiResult<T>` typed from `src/lib/api/schema.d.ts` (generated by `openapi-typescript` from `backend/openapi.json`); base URL from `NEXT_PUBLIC_API_BASE_URL`; network errors mapped to `{ok:false,error:{code:"NETWORK_ERROR",retryable:true}}`.

- [ ] **Step 1: Write failing Playwright smoke test**: landing page shows heading "MISSIONFORGE", the text "independent educational prototype", and a backend-status chip reading "Engine 0.1.0" fetched via `/api/health`.
- [ ] **Step 2: Run** `pnpm test:e2e` (with backend running) → FAIL.
- [ ] **Step 3: Implement** scaffold, `export_openapi.py` (writes `backend/openapi.json` from `app.openapi()`), `gen:api` (`openapi-typescript`), dark mission-control design tokens (midnight/graphite, cyan/amber accents), `Disclaimer` footer on every page. Pin exact versions; commit lockfile.
- [ ] **Step 4: Run** `pnpm lint && pnpm typecheck && pnpm build && pnpm test:e2e` → PASS.
- [ ] **Step 5: Commit** `feat(frontend): Next.js shell, generated API types, smoke e2e`

### Task 0.3: CI + check scripts

**Files:** Create `.github/workflows/ci.yml`, `scripts/check_all.sh`, `scripts/check_all.ps1`

- [ ] **Step 1:** Script runs, in order: `uv run ruff check . && uv run mypy app && uv run pytest -q && uv run python -m scripts.validate_catalog` (backend; validator stub exits 0 until Task 1.4) then `pnpm lint && pnpm typecheck && pnpm build` (frontend); fails fast with non-zero exit.
- [ ] **Step 2:** CI workflow: matrix job per side; cache `uv` and `pnpm`; separate job for Playwright (starts uvicorn + `pnpm start`); fails PRs on any step.
- [ ] **Step 3: Verify** `scripts/check_all.sh` exits 0 locally. **Commit** `chore: CI and check scripts (G0)`.

---

# Phase 1 — Contracts, Units, Catalogue, Scenarios (M06, M07)

### Task 1.1: Units, provenance, quantity, conversions

**Files:**
- Create: `backend/app/schemas/units.py`, `backend/app/domain/units/{constants,conversions,guards}.py`
- Test: `backend/tests/unit/units/test_conversions.py`, `test_guards.py`

**Interfaces:**
- Produces: `Fidelity`, `Unit` literal (exactly the list in architecture §6.2), `Provenance`, `Uncertainty`, `Quantity` (spec §6.2 fields); `constants.G0=9.80665`, `C=299792458.0`, `KB=1.380649e-23`, `MU_EARTH=3.986004418e14`, `R_EARTH=6378137.0`, `SOLAR_CONSTANT_W_M2` (flag gameplay-estimate unless sourced), `AU_M`; `km_to_m`, `m_to_km`, `kms_to_ms`, `ms_to_kms`, `wh_to_j`, `j_to_wh`, `day_to_s`, `s_to_day`, `deg_to_rad`, `db_to_ratio`, `ratio_to_db`, `dbw_to_w`, `to_si(q: Quantity) -> Quantity`; `guards.require_finite(x, name)`, `require_positive`, `require_fraction` raising `DomainValidationError(code, field, message)`.

- [ ] **Step 1: Write failing tests** with known answers: `km_to_m(1.5)==1500`; `kms_to_ms(2.5)==2500`; `wh_to_j(1)==3600`; `day_to_s(1)==86400`; `ratio_to_db(100)==approx(20)`; `db_to_ratio(3.0103)==approx(2,rel=1e-4)`; `require_finite(float("nan"),"x")` and `inf` raise with `field=="x"`; `to_si` of `Quantity(1,"km")` returns `1000 "m"` and preserves provenance; round-trip property for every converter pair.
- [ ] **Step 2: Run** `uv run pytest tests/unit/units -v` → FAIL.
- [ ] **Step 3: Implement** modules; reject `bool`, `NaN`, `±inf`, numeric strings (no coercion: `ConfigDict(strict=True)` on `Quantity.value`).
- [ ] **Step 4: Run** → PASS, coverage ≥ 90 %. **Step 5: Commit** `feat(domain): units, provenance, conversions`

### Task 1.2: MissionState and mission schemas

**Files:**
- Create: `backend/app/schemas/mission.py`, `backend/app/schemas/trajectory.py`, `backend/app/domain/mission/{validation,migrations,defaults}.py`
- Test: `backend/tests/unit/mission/test_mission_state.py`, `test_validation.py`, `test_migrations.py`

**Interfaces:**
- Produces: all models in architecture §6.2 (`MeasurementRequirement … MissionState`, `ScienceObjective`, `ComponentSelection`, `Destination`, `TrajectorySelection`, `SpacecraftArchitecture`, `ObservationPlanItem`, `DownlinkPlanItem`, `OperationsPlan`, `MissionConstraints`); `validate_mission_state(state, catalog) -> list[ValidationIssue]` (cross-refs: component IDs exist, observation `measurement_id` exists, unique IDs, `arrival_date >= departure_date`, fractions in [0,1]); `migrate_mission(raw: dict) -> dict` (v1 identity; unknown version raises `UnsupportedSchemaVersion`); `sanitize_title(str) -> str` (strip control chars/HTML, ≤ 80 chars).
- `MissionState` holds **no derived totals** (test asserts no field named `*_total*`, `score`, `feasible`).

- [ ] **Step 1: Write failing tests**: parses camelCase JSON and snake_case via `populate_by_name`; `extra="forbid"` rejects unknown field; duplicate objective IDs → issue `DUPLICATE_ID`; `OperationsPlan.observation_plan[0].measurement_id="nope"` → `UNKNOWN_MEASUREMENT`; `duty_cycle=1.2` → validation error; `title="<script>x</script>"` sanitised; `schema_version="2.0"` → `UnsupportedSchemaVersion`.
- [ ] **Step 2–4:** run (FAIL) → implement → run (PASS).
- [ ] **Step 5: Commit** `feat(schemas): MissionState and validation (M06)`

### Task 1.3: Analysis / simulation / API / evidence schemas (contract freeze)

**Files:**
- Create: `backend/app/schemas/{catalog,analysis,simulation,optimization,uncertainty,science_belief,operations,evidence}.py`
- Test: `backend/tests/contract/test_schema_freeze.py`, `test_openapi_roundtrip.py`

**Interfaces:**
- Produces (exactly the field sets in the spec): `FailureMode`, `CompatibilityRule`, `CatalogComponent`; `SuggestedAction`, `ConstraintResult`, `BudgetAnalysis`, `ScienceAnalysis`, `ReliabilityAnalysis`, `MissionAnalysis` (+ `feasibility: Literal["feasible","marginal","infeasible"]`, `score: ScoreBreakdown`, `top_drivers: list[str]`, `assumptions: list[str]`); `MissionEvent`, `TelemetrySample(channel, unit, mission_day, value, fidelity)`, `Phase`, `DecisionRecord(event_id, choice_id, decision_maker: Literal["ground","onboard-policy","player"])`, `MissionRun(run_id, mission_id, design_revision, seed, scenario_event_set_id, engine_version, catalog_version, events, telemetry, decisions, science_outcomes, final_report)`; `SimulationInput`; `ArchitectureNode/Edge`, `OptimizationObjective`, `ArchitectureCandidate`, `TradeStudyResult`; `DistributionSpec`, `UncertainParameter`, `MetricQuantiles`, `RobustnessResult`; hypothesis/belief models; `ObservationOpportunity`, `ContactWindow`, `ScheduledDataCycle`, `MissionSchedule`; `EvidenceRecord`, `MissionRunManifest`, `MissionPackage`.
- Resolve doc discrepancies here (see Decisions D1–D4) and record them in `backend/app/schemas/CONTRACTS.md`.

- [ ] **Step 1: Write failing tests**: every schema JSON-round-trips; a golden snapshot of `MissionAnalysis.model_json_schema()` field names is committed (`tests/contract/snapshots/*.json`) and the test fails on drift; OpenAPI generated from app contains every route-referenced schema; `ApiResult` generic serialises with `meta.requestId`.
- [ ] **Step 2–4:** run → implement → run.
- [ ] **Step 5: Commit** `feat(schemas): freeze Interface v1 (G1 part 1)`. After this commit, shared schemas are **protected**.

### Task 1.4: Catalogue data, loader, validator

**Files:**
- Create: `data/catalog/*.json` (10 category files + `catalog_manifest.json`), `backend/app/domain/catalog/{loader,resolver,compat}.py`, `backend/scripts/validate_catalog.py`
- Test: `backend/tests/contract/test_catalog_contract.py`, `backend/tests/unit/catalog/test_compat.py`

**Interfaces:**
- Produces: `load_catalog(path: Path) -> Catalog` (immutable; `.get(id)`, `.by_category(c)`, `.version`); `resolve_architecture(arch, catalog) -> ResolvedArchitecture` (raises `CatalogItemNotFound`); `check_compatibility(components) -> list[CompatibilityIssue]`; CLI `python -m scripts.validate_catalog` exits 1 on schema error, unresolved reference, non-finite value, missing provenance, or conflicting masses for the same bus interface.

**Content requirements:** 3–5 options for launch (with `launch_mass_limit`, `c3_capability` for a reference C3), bus, propulsion (chemical monoprop/biprop, electric, cold gas – `isp_s`, `thrust_n`, `dry_mass_kg`, `power_w`), power (array area/efficiency, battery `capacity_wh`, `usable_dod`), ADCS (`pointing_accuracy_deg`, `power_w`, `mass_kg`), comms (`tx_power_w`, `antenna_gain_dbi`, `frequency_hz`, `required_ebn0_db`, `implementation_loss_db`), thermal, C&DH (`storage_bits`), 4–5 instruments (`mass_kg`, `power_w`, `data_rate_bps`, `capabilities[]`, `pointing_requirement_deg`), ground (`station_gain`, `noise_temp_k`, `contact_availability`). Each parameter has per-parameter provenance. Values from NASA SmallSat SoA 2026 chapters may be used **only after opening the primary table**; otherwise mark `gameplay-estimate` and `is_illustrative=true`. No invented vendors.

- [ ] **Step 1: Write failing tests**: every file validates against `CatalogComponent`; all `compatible_with` IDs resolve; every `Quantity` finite with unit; every illustrative record has `fidelity=="gameplay-estimate"`; validator returns non-zero for a fixture with a broken reference (`tests/fixtures/catalog_broken/`); at least one instrument/antenna/battery swap changes the mass analysis (assert later in Task 2.8 — placeholder skipped test referencing it).
- [ ] **Step 2–4:** run → author data + loader → run (PASS). Add validator to `scripts/check_all.*` (replace stub).
- [ ] **Step 5: Commit** `feat(data): catalogue v0.1.0, loader and validator (M07)`

### Task 1.5: Scenario templates + default NEO MissionState

**Files:**
- Create: `data/missions/neo-rendezvous.json` (P0), `lunar-polar-scout.json`, `earth-observation.json` (P1/P2), `backend/app/domain/mission/defaults.py`, `backend/app/services/template_service.py`
- Test: `backend/tests/contract/test_mission_templates.py`

**Interfaces:**
- Produces: `list_templates() -> list[ScenarioTemplate]`, `default_mission_state(scenario_id, *, mission_id, seed) -> MissionState`.

**Content:** NEO: 2–4 objectives (surface morphology/shape, VNIR spectral properties, thermal behaviour, optional magnetic/plasma), each with ≥ 1 `MeasurementRequirement` (stable IDs, capability strings matching instrument `capabilities`), a trajectory preset flagged `scenario-preset` (replaced by JPL option in Phase 5), a deliberately **tunable starter design** that produces one clear data-buffer warning fixable by changing antenna or duty cycle (needed for the demo). Lunar/EO: curated presets with explicit "orbit: two-body circular educational preset" notes.

- [ ] **Step 1: Write failing tests**: each template parses; resolves against catalogue; `validate_mission_state` returns zero issues; NEO starter has exactly 2 objectives; no derived totals present; deterministic `default_mission_state` (same args ⇒ equal object).
- [ ] **Step 2–4:** run → author → run. **Step 5: Commit** `feat(data): scenario templates (G1)`

---

# Phase 2 — Engineering Engine (M08) — `backend/app/domain/analysis/**`

Common rule for 2.1–2.7: each module is a pure function returning a typed result with `assumptions: list[str]`, `model_id: str` (e.g. `"mass-v1"`), `Provenance(fidelity="derived")`; invalid input raises `DomainValidationError`; the orchestrator (2.8) converts errors to `ConstraintResult(status="fail")`. Bump `ENGINE_VERSION` on any equation change.

### Task 2.1: Mass budget

**Files:** Create `analysis/mass.py` · Test `tests/unit/analysis/test_mass.py`
**Interfaces:** `compute_mass_budget(resolved: ResolvedArchitecture, propellant_kg: float, margin_fraction: float, launch_limit_kg: float | None) -> MassResult(payload_kg, subsystem_dry_kg, dry_kg, wet_kg, allocated_kg, margin_to_limit_fraction, top_contributors: list[(id, kg)])`.

- [ ] **Step 1: Tests:** payload 10 + subsystems 90 + propellant 40, margin 0.2 → dry 100, wet 140, allocated 168; limit 200 → margin_to_limit 0.16; limit 150 → −0.12; quantity=2 instrument doubles its mass; top contributors cover ≥ 80 % of mass in descending order; no generic structure % added (bus with structure mass 20 → total unchanged by any hidden factor); negative mass / NaN → `DomainValidationError`; no instruments → payload 0 (not error).
- [ ] **Step 2–4:** run → implement → run. **Step 5: Commit.**

### Task 2.2: Propulsion / delta-v

**Files:** `analysis/propulsion.py` · `tests/unit/analysis/test_propulsion.py`
**Interfaces:** `delta_v_ms(isp_s, m0_kg, mf_kg) -> float`; `propellant_for_delta_v(isp_s, mf_kg, dv_ms) -> float`; `maneuver_budget(prop: ResolvedPropulsion, dry_kg, required: list[Maneuver], reserve_ms) -> ManeuverBudget(available_ms, required_ms, margin_ms, per_maneuver)`; `Maneuver(id, dv_ms, source: "spacecraft"|"trajectory-info")` — **only `source=="spacecraft"` counted**.

- [ ] **Step 1: Tests:** Isp 300, m0/mf = 2 → 2039.2 m/s (±0.5); inverse: mf 100 kg, dv 2039.2 → propellant ≈ 100 kg (±0.1); `m0<=mf`, `isp<=0`, `mf<=0` raise; maneuver list containing a trajectory-info item with 6 km/s does **not** change `required_ms` (guards against adding JPL `dv_tot`/C3); reserve exhaustion reports which maneuver consumes it; electric propulsion flags `thrust_time_days` warning (long burn) when thrust data present.
- [ ] **Step 2–4:** run → implement → run. Commit.

### Task 2.3: Power & energy

**Files:** `analysis/power.py` · `tests/unit/analysis/test_power.py`
**Interfaces:** `average_power_w(loads: list[Load]) -> float` (Σ P·duty); `peak_power_w(loads)`; `solar_generation_w(flux_w_m2, area_m2, cell_eff, eps_eff, incidence_rad)`; `solar_flux_at(distance_au) -> float` (= constant / d²); `energy_ledger(phases: list[PowerPhase], battery: Battery) -> EnergyLedger(per_phase: list[PhaseEnergy], min_soc_fraction, closes: bool)` with `battery_next = clamp(b + gen − cons, 0, cap)` and usable-DoD floor enforced.

- [ ] **Step 1: Tests:** loads (10 W @0.5, 20 W @1.0) → avg 25 W, peak 30 W reported separately; flux at 2 AU = constant/4; incidence 60° halves generation; eclipse 35 min @ 40 W, DoD 0.8, discharge eff 0.9 → required battery ≈ 40·(35/60)/0.72 ≈ 32.4 Wh (±0.1); battery clamps at 0 and at capacity; passes average but fails peak (peak > regulated supply) ⇒ constraint fails; Wh vs W units never mixed (type-level `Quantity` unit asserts).
- [ ] **Step 2–4:** run → implement → run. Commit.

### Task 2.4: Data & communications

**Files:** `analysis/data.py`, `analysis/comms.py` · `tests/unit/analysis/test_data.py`, `test_comms.py`
**Interfaces:** `fspl_db(range_m, freq_hz)`; `link_budget(LinkInput) -> LinkResult(fspl_db, pr_dbw, cn0_dbhz, ebn0_db, margin_db, capacity_bps)`; `data_ledger(observations, contacts, buffer_capacity_bits, protocol_eff, compression) -> DataLedger(generated_bits, downlinked_bits, buffer_timeline, peak_buffer_bits, overflow_bits, margin_fraction)`.

- [ ] **Step 1: Tests:** 10× range ⇒ +20.0 dB (±1e-9); 2× frequency ⇒ +6.0206 dB; margin = Eb/N0 − required; `buffer_end = max(0, start + gen − down)` and never exceeds capacity without `overflow_bits > 0` flagged; downlinked ≤ min(contact capacity, buffer contents) (so cannot downlink data not yet generated); **zero contacts ⇒ downlinked 0, backlog = generated, no div-by-zero**; negative link margin contact contributes 0 capacity; unit mismatch (dBW vs W) caught.
- [ ] **Step 2–4:** run → implement → run. Commit.

### Task 2.5: Science coverage

**Files:** `analysis/science.py` · `tests/unit/analysis/test_science.py`
**Interfaces:** `science_coverage(objectives, instruments, observation_plan, data_ledger, pointing, power_ok) -> ScienceAnalysis` where `achieved_fraction = capability_match × min(1, scheduled_hours / required_hours) × pointing_ok × returned_fraction`; reports `collected_fraction` and `returned_fraction` separately; `missing_requirements`.

- [ ] **Step 1: Tests:** instrument lacking required capability contributes 0 to that requirement (spec test); objective coverage = Σ w·a / Σ w; science score = 100·Σ priority·coverage / Σ priority; no instruments ⇒ score 0 and every required measurement in `missing_requirements`; collected but un-downlinked data lowers `returned_fraction` only; objective with Σ weights 0 ⇒ validation error, not NaN.
- [ ] **Step 2–4:** run → implement → run. Commit.

### Task 2.6: Cost, reliability, thermal, orbital

**Files:** `analysis/{cost,reliability,thermal,orbital}.py` · `tests/unit/analysis/test_{cost,reliability,thermal,orbital}.py`
**Interfaces:** `cost_estimate(resolved, ops_days, scenario_params) -> CostBreakdown(hardware, launch, operations, ground, reserves, development, total, low, high)` all `gameplay-estimate` unless catalogue sourced; `reliability(resolved) -> ReliabilityAnalysis` (R=Π R_i with stated independence assumption, `rpn = occurrence·severity·detectability` labelled heuristic, single-point-failure list); `thermal_check(resolved, scenario) -> ConstraintResult(status in {"pass","warning","not-modelled"})` (never emits a temperature); `circular_orbit_period_s(altitude_m)`, `circular_orbit_velocity_ms`.

- [ ] **Step 1: Tests:** LEO 500 km period ≈ 5677 s (±3 s) and velocity ≈ 7612 m/s (±5); cost total = Σ components, label `gameplay-estimate`, low ≤ nominal ≤ high; thermal result never `"pass"` without inputs (returns `not-modelled`); common-cause note present in reliability assumptions; RPN is not reported as a probability.
- [ ] **Step 2–4:** run → implement → run. Commit.

### Task 2.7: Constraints, score, top drivers

**Files:** `analysis/{constraints,score,drivers}.py` · tests `test_constraints.py`, `test_score.py`
**Interfaces:** `evaluate_constraints(ctx: AnalysisContext) -> list[ConstraintResult]` (IDs: `mass-launch-limit`, `mass-margin`, `delta-v-margin`, `peak-power`, `energy-closure`, `battery-reserve`, `data-buffer`, `link-margin`, `compat-*`, `science-mandatory-coverage`, `trajectory-valid`, `budget`, `thermal`); each with actual/limit/margin_fraction, `impacted_subsystems`, `suggested_actions`; `feasibility(constraints) -> Literal[...]`; `score_preview(analysis) -> ScoreBreakdown` with weights 30/25/20/15/10 returned in the output; `top_drivers(constraints, sensitivities) -> list[str]`.

- [ ] **Step 1: Tests:** mass over limit ⇒ `feasibility=="infeasible"`, score still computed, `mission_ready is False` (AC-04); `not-modelled` never maps to `pass`; every `fail/warning` has non-empty `explanation` and ≥ 1 `impacted_subsystems`; score weights sum to 100; score never rewards lower price alone (two designs equal except cost, higher cost does not lower resource-stewardship if still in budget — define & test the formula); hard fail ⇒ `mission_ready False` regardless of score 99.
- [ ] **Step 2–4:** run → implement → run. Commit.

### Task 2.8: `analyze_mission` orchestrator + golden fixtures

**Files:** `analysis/orchestrator.py` · `tests/unit/analysis/test_orchestrator.py`, `tests/golden/neo_default_analysis.json`, `tests/unit/analysis/test_performance.py`
**Interfaces:** `analyze_mission(state: MissionState, catalog: Catalog, *, engine_version: str, now: datetime) -> MissionAnalysis` — `now` injected so `calculated_at` is the only non-deterministic field.

- [ ] **Step 1: Tests:** (a) default NEO analysis equals golden JSON excluding `calculatedAt`; (b) adding a spectrometer (mass, power, data-rate all > 0) changes `budgets.dry_mass`, `average_power`, `data_generated`, `estimated_cost`, `science.coverage_score` (AC-03); (c) swapping antenna changes link margin and `data_margin_fraction`; (d) repeated calls identical; (e) a catalogue item referenced but missing yields `CATALOG_ITEM_NOT_FOUND`-mapped failure result, not an exception to the route; (f) p95 over 200 runs < 100 ms; (g) hypothesis: no `NaN`/`inf` anywhere in serialised output (recursive walk).
- [ ] **Step 2–4:** run → implement (resolve → mass → propulsion → power → data/comms → science → cost/reliability/thermal → constraints → score → drivers; fills `assumptions`) → run. **Gate G2 backend half.**
- [ ] **Step 5: Commit** `feat(domain): analyze_mission engine (M08)`; bump to `ENGINE_VERSION=0.1.0` golden.

---

# Phase 3 — API and Mission Architect UI (M16 core, M01, M02)

### Task 3.1: Catalogue/templates/validate routes + service layer

**Files:** Create `backend/app/services/{mission_service,catalog_service}.py`, `backend/app/api/routes/{catalog,templates,missions}.py`, `backend/app/api/errors.py` · Test `backend/tests/integration/test_routes_mission.py`
**Interfaces:** `GET /api/catalog`, `GET /api/templates`, `POST /api/mission/validate {missionState} → {analysis}`; error mapping table: `ValidationError→VALIDATION_ERROR (422 body, ok:false)`, `CatalogItemNotFound→CATALOG_ITEM_NOT_FOUND`, infeasible design → **`ok:true`** with `feasibility` (not an API error), unexpected → `INTERNAL_ERROR` with request id.

- [ ] **Step 1: Tests:** valid default NEO → `ok true`, analysis present, revision echoed; bad body → `VALIDATION_ERROR` with field paths; unknown component → `CATALOG_ITEM_NOT_FOUND`; infeasible state still `ok:true`; response never contains raw exception text; `title` with HTML sanitised before echo; payload > configured size → 413.
- [ ] **Step 2–4:** run → implement → run. Re-export OpenAPI, regenerate TS types. Commit.

### Task 3.2: Shell, routing, workspace (M01)

**Files:** `frontend/src/app/**` routes, `components/shell/*`, `state/mission-store.ts`, `state/selectors.ts`, `components/common/{FidelityBadge,ProvenancePopover,ConstraintBadge,StatusPill}.tsx`
**Interfaces:** `useMissionStore`: `{ mission: MissionState|null, designRevision, analysis, analysisRevision, status: 'idle'|'calculating'|'stale'|'error', dirty }` + actions `loadTemplate(id)`, `selectComponent(category,id)`, `updateObjective`, `updateOperations`, `updateConstraints`, `commitRevision()`. Types come from `src/lib/api/schema.d.ts` only.

- [ ] **Step 1: Playwright tests:** direct URL `/architect/<id>` after refresh restores mission; unknown ID shows not-found state with a "Start a mission" action; scenario cards (3) on landing, only NEO enabled until Task 7.1 (others labelled "preview"); no layout overflow at 375 px; `ConstraintBadge` renders icon **and** text for pass/watch/fail/not-modelled (never colour alone).
- [ ] **Step 2–4:** run → implement → run. Commit.

### Task 3.3: Mission brief + science traceability panel (M02a)

**Files:** `components/mission-brief/*`, `components/science-traceability/*`
- [ ] **Step 1: Tests (component + e2e):** onboarding shows one-sentence scenario, top-3 constraints, "starter design" label, 2–3 objective confirm; traceability table lists objective → requirement → instrument with an explicit "UNCOVERED" row when no instrument matches (AC-02); landing → editable mission < 90 s (measured in e2e, assert < 90 000 ms).
- [ ] **Step 2–4:** implement from `MissionState` + `analysis.science` (later replaced by graph from 6.1). Commit.

### Task 3.4: Architect page, live budgets, stale-response protection (M02b)

**Files:** `components/architect/*`, `components/budgets/*`, `src/hooks/useAnalysis.ts`
**Interfaces:** `useAnalysis(mission)`: debounced 150 ms; each request tagged with `designRevision`; response applied only if `response.designRevision === store.designRevision`; `AbortController` cancels superseded requests; failure keeps last good analysis visibly marked "stale"; never renders missing as 0 (shows "—" + reason).

- [ ] **Step 1: Tests (Playwright with `page.route` delay injection):** (a) revision-1 response delayed past revision-2 response → UI shows revision-2 numbers (Review Focus #2); (b) API 500 → "Analysis failed — retry" and last good values marked stale; (c) component swap highlights affected budget tiles (mass, power, data); (d) constraint card shows actual, limit, margin, impacted subsystem, ≥ 1 action; (e) a dependent replacement needed by compatibility asks confirmation before changing selections (prod §8.3); (f) keyboard-only completion of one component swap.
- [ ] **Step 2–4:** run → implement (layout 22/48/30 desktop, stacked mobile; fidelity badge + provenance popover on every numeric) → run. Commit. **Gate: Phase 3 exit.**

### Task 3.5: Trade-study route + compare view (2 designs)

**Files:** `backend/app/api/routes/missions.py` (`POST /api/mission/trade-study`, ≤ 3 alternatives), `components/arena/CompareTable.tsx`
- [ ] **Step 1: Tests:** 3 alternatives < 300 ms; 4 → `VALIDATION_ERROR`; deltas = alt − base per metric; original baseline untouched; UI shows per-metric delta with direction icon. **Step 2–4** implement. Commit.

---

# Phase 4 — Simulation, Control, Review, Persistence (M14, M03, M04, M18)

### Task 4.1: Deterministic PRNG, phases, events, nominal run

**Files:** `domain/simulation/{prng,phases,events,telemetry,runner,report}.py` · Tests `tests/unit/simulation/*`, `tests/golden/neo_run_seed42.json`
**Interfaces:** `make_rng(master_seed: int, *labels: str) -> random.Random` (SHA-256 of `f"{seed}:{labels}"` → seed); `run_mission(sim_input: SimulationInput, catalog, *, decisions: dict[str, str] | None = None) -> MissionRun`; phases (≥ 6): `launch-deployment, commissioning, cruise, mid-course, approach, science-ops, downlink-return, complete|terminated`; events sorted by `(mission_day, sequence)`; telemetry checkpoints ≥ 3 channels (battery SoC, propellant fraction, buffer usage, link margin, pointing error) generated from `MissionAnalysis` + phase state; `MissionRun` immutable (`frozen=True`).

- [ ] **Step 1: Tests:** same input twice ⇒ identical `model_dump_json()` (AC-11); run equals golden; every event has stable `id`, severity, explanation, `trigger` referencing a design weakness or declared scenario event; ties in `mission_day` ordered by sequence; infeasible design with `experimental=False` ⇒ `LAUNCH_BLOCKED` (no run), with `experimental=True` ⇒ run flagged `experimental`; `run.design_revision == state.design_revision`; run unaffected by anything resembling playback speed (no time import; test greps module for `time.`/`datetime.now`).
- [ ] **Step 2–4:** run → implement → run. Commit.

### Task 4.2: Anomalies, decisions, early termination, science outcome

**Files:** `simulation/{anomalies,decisions}.py` · tests `test_anomalies.py`, `test_decisions.py`
**Interfaces:** `scenario_events` loaded from `data/scenarios/neo-rendezvous.events.json` (event-set ID `neo-default-v1`); `Decision(event_id, prompt, choices: list[Choice(id,label,effect: dict, tradeoff)] )` with ≥ 2 decisions each with ≥ 2 choices of **measurably different** consequences (science days lost, power, risk); `apply_decision(run_state, event_id, choice_id)`; `science_outcomes(run_state) -> collected vs returned`.

- [ ] **Step 1: Tests:** a low-margin comms design triggers `missed-contact → data-backlog` anomaly traced via `trigger`; a design with ample margin does **not** (no random punishment); choosing `pause-science` vs `continue` yields different `returned_fraction` and different final report; invalid choice ID → error; abort path produces `terminated` run with postmortem report (learning journey preserved); same seed + same decisions ⇒ identical; different seed ⇒ differs only in seeded uncertainty events.
- [ ] **Step 2–4:** run → implement → run. Commit.

### Task 4.3: Simulate route + interactive decision API

**Files:** `routes/missions.py` (`POST /api/mission/simulate`, `POST /api/mission/run/{runId}/decision`), `services/simulation_service.py` (in-memory run store keyed by run ID, bounded LRU 50)
- [ ] **Step 1: Tests:** returns `{analysis, run, telemetry, events, finalReport}`; `monteCarloSamples > cap` → `SIMULATION_LIMIT_EXCEEDED`; unknown run → 404 envelope; payload/time budget enforced; run immutable (second decision call on a completed decision rejected). **Step 2–4** implement. Commit.

### Task 4.4: Mission Control UI (M03) + Review UI (M04 basic)

**Files:** `components/mission-control/*`, `components/review/*`, `app/control/[runId]`, `app/review/[runId]`
- [ ] **Step 1: Playwright tests:** phase ribbon shows ≥ 6 phases; events list shows id/time/severity/why; telemetry charts share a time axis with units; playback at 0.5×/1×/4× produces identical final report text (hash compared); decision card requires a choice, and the choice appears in the log and the review; review shows objectives met/partial/missed, collected vs returned, five score dimensions with the weights, margins chart, root causes ranked, ≥ 1 counterfactual (initially from Task 4.6 stub, replaced by 6.8), data limitations section; WebGL absent ⇒ 2D fallback (`page.addInitScript` disabling WebGL).
- [ ] **Step 2–4:** implement playback as a client-side iterator over the immutable event list (no physics). Commit.

### Task 4.5: Persistence, import/export, replay (M18)

**Files:** `frontend/src/lib/persistence/{storage,package,replay}.ts`, backend `schemas/evidence.py`, `routes/missions.py` (`POST /api/mission/import` validate+migrate), tests `frontend/tests/e2e/persistence.spec.ts`, `backend/tests/integration/test_import.py`
**Interfaces:** `saveMission(state)` (debounced 400 ms, IndexedDB→localStorage fallback in try/catch); `exportPackage() -> Blob(JSON of MissionPackage)`; `importPackage(file) -> Result` — always round-trips through `POST /api/mission/import`; `replayStatus(run, currentVersions) -> "identical-replay" | "version-mismatch"`.

- [ ] **Step 1: Tests (Review Focus #4, #5):** reload restores latest design; export → import round-trip equals original `MissionState`; invalid JSON, `{"schemaVersion":"9.9"}`, `NaN` literal, 20 MB file, `title` with `<img onerror>` ⇒ rejected/sanitised with explanation and **current mission untouched**; quota error (stub `setItem` throw) ⇒ export prompt, UI keeps running; engine version changed in import ⇒ banner "version mismatch — not an identical replay" and no "identical" label; same versions ⇒ replay produces equal event IDs/order/telemetry/decisions (AC-11, AC-13, §12.6).
- [ ] **Step 2–4:** implement. Commit. **Gate G3 achieved when 3.x + 4.1–4.5 e2e passes: full vertical slice (prod AC-01…AC-14 subset).**

### Task 4.6: Evidence Passport v1 (JSON + HTML)

**Files:** `domain/dossier/{build_run_manifest,export_mission_dossier}.py`, `routes/missions.py` (`POST /api/mission/dossier`), `components/review/ExportDossier.tsx`
- [ ] **Step 1: Tests:** manifest contains `schemaVersion, engineVersion, catalogVersion, scenarioVersion, eventSetId, seed, appVersion`; every external (JPL) value in dossier has source link or explicit "unavailable-source"; JSON validates as `MissionPackage`; re-importing reproduces the same nominal run; HTML escapes all user strings; includes limitations + non-endorsement text; deterministic (byte-equal apart from `exportedAt`).
- [ ] **Step 2–4:** implement (HTML template string, print stylesheet). Commit.

---

# Phase 5 — JPL Adapter (M17)

### Task 5.1: Models, normaliser, fixtures

**Files:** `integrations/jpl/{models,normalize}.py`, `backend/tests/fixtures/jpl/{mode_a_ok.json,mode_q_ok.json,unknown_version.json,short_row.json}`, `tests/contract/test_jpl_normalize.py`
**Interfaces:** `normalize_mode_a(raw: dict) -> list[JplMissionOption]` (index by `fields` names; **never positional**); `SUPPORTED_SIGNATURE_VERSIONS = {"1.2"}` (verify against live docs when capturing the fixture); km/s kept in model, converted at boundary.

- [ ] **Step 1: Tests:** correct mapping of c3, v∞ dep/arr, dv_tot, tof; reordered `fields` still maps correctly; missing required field ⇒ `JPL_SCHEMA_UNSUPPORTED`; unknown version ⇒ `JPL_SCHEMA_UNSUPPORTED`; rows shorter than `fields` skipped with a counted warning (Review Focus #3); `source.fidelity=="source-backed"` only on returned fields.
- [ ] **Step 2–4:** capture one real fixture per mode (Task 5.3 script, fair-use compliant), implement. Commit.

### Task 5.2: Client, serial queue, cache, repository

**Files:** `integrations/jpl/{client,repository}.py`, `infrastructure/queue/serial_queue.py`, `infrastructure/cache/ttl_cache.py`, tests `tests/unit/infrastructure/*`, `tests/integration/test_jpl_repository.py` (respx)
**Interfaces:** `SerialQueue.submit(coro_factory)` (asyncio.Lock/queue, concurrency 1); `TtlCache.get/set(key, value, ttl)` with `get_stale`; `JplRepository.neo_accessible(params) -> SourceResult[list[JplMissionOption]]` where `SourceResult.status ∈ {"live","cached","demo"}`; params validated against allow-listed `years`, `criterion`, `limit ≤ 100`, designation regex.

- [ ] **Step 1: Tests:** 20 concurrent calls ⇒ upstream sees max 1 in flight and identical params hit upstream once; User-Agent equals `MISSIONFORGE/0.1.0 (contact)`; 429 with `Retry-After: 2` ⇒ waits ≥ 2 s (patched sleep) then retries with capped backoff, max N attempts; 404/400 not retried; timeout 10 s ⇒ stale cache with `status="cached"`; no cache + failure ⇒ demo snapshot `status="demo"` and `retrieved_at` of capture; unknown version ⇒ same fallback; designation `"; rm -rf"` rejected before any request; cache key includes mode+all params; logs contain no user data.
- [ ] **Step 2–4:** implement. Commit.

### Task 5.3: Routes, snapshot capture, UI target picker

**Files:** `routes/space_data.py` (`GET /api/space-data/neo-accessible`, `GET /api/space-data/neo/{designation}`), `backend/scripts/capture_demo_data.py`, `public/data/demo-jpl-snapshot.json`, `components/mission-brief/TargetPicker.tsx`
- [ ] **Step 1: Tests:** routes return normalised data + `meta.sourceStatus`; **no raw upstream key names** in response; Playwright asserts every network request host is the MISSIONFORGE API (no `ssd-api.jpl.nasa.gov`); offline run (backend env `JPL_FORCE_OFFLINE=1`) shows badge "DEMO — captured <date>", never "LIVE"; picking a target writes `trajectory` (`provider:"jpl-mdesign"`, `raw_source_ref`) into `MissionState` and updates mass/ΔV/comms ranges without adding C3 to ΔV (AC-08, AC-09, §12.7).
- [ ] **Step 2–4:** implement; capture one snapshot with the User-Agent and sequential requests; validate snapshot with the normaliser in CI. Commit. **Gate G5.**

---

# Phase 6 — Research Differentiators (M09–M13, M15, Analyst)

### Task 6.1: Architecture graph + impact trace (FR-15, FR-16, AC-15)

**Files:** `domain/architecture_graph/*`, `routes/missions.py` (`POST /api/mission/graph`, `POST /api/mission/impact`), `components/science-traceability/GraphExplorer.tsx` · tests `tests/unit/architecture_graph/*`
**Interfaces:** `build_architecture_graph(state, analysis) -> ArchitectureGraph(nodes, edges)`; `trace_impact(before: MissionAnalysis, after: MissionAnalysis, graph) -> ImpactReport(changed_metrics, newly_violated, improved, affected_objectives)`; `build_traceability_matrices(graph) -> (STM, MTM)`.

- [ ] **Step 1: Tests:** removing the only spectrometer ⇒ its requirement node `uncovered`, objective expected coverage falls; payload data-rate increase ⇒ path instrument → data metric → data-buffer constraint exists; stable node IDs for unchanged state; no edge references a missing node; every edge has `kind` + non-empty `rationale`; deterministic; does not mutate state; STM/MTM consistent with entities.
- [ ] **Step 2–4:** implement; UI: select node highlights up/down-stream; "Why did this change?" list after an edit. Commit.

### Task 6.2: Pareto explorer / Mission Design Arena (FR-17, FR-18, AC-16)

**Files:** `domain/optimization/*`, `routes/missions.py` (`POST /api/mission/optimize`), `components/arena/*`, `app/arena/[missionId]` · tests `tests/unit/optimization/*`
**Interfaces:** `generate_candidates(base, catalog, *, seed, cap) -> list[MissionState]` (baseline + single swaps + two-way swaps + seeded sample; stable IDs from content hash; cap 100–250; fewer if fewer legal combos); `dominates(a: list[float], b: list[float]) -> bool` (minimise-normalised); `pareto_front(cands) -> list[Candidate]`; `select_archetypes(feasible, objectives) -> {lean, science_max, resilient}` with `explanation`.

- [ ] **Step 1: Tests:** A dominates B only if ≤ on all and < on one; identical vectors don't dominate each other; infeasible never in frontier/archetypes but listed under `near_misses` with violations; same input+seed ⇒ identical IDs/front/archetypes; Lean has min cost among feasible, Science-max has max science, Resilient has max `probability_feasible` proxy (uses 6.3 with ≤ 50 samples; until then max reserve-margin proxy flagged); ≥ 100 candidates on NEO default; 250 candidates < 3 s; objective weights shown but never used for dominance.
- [ ] **Step 2–4:** implement; UI: Pareto scatter (cost vs science), click loads candidate into Architect, side-by-side compare explaining subsystem differences. Commit.

### Task 6.3: Robustness lab (FR-19, AC-17)

**Files:** `domain/uncertainty/{samplers,paths,wilson_interval,run_robustness}.py`, `data/uncertainty/default_profile.json`, `routes/missions.py` (`POST /api/mission/robustness`), `components/robustness/*`
**Interfaces:** `sample(dist: DistributionSpec, rng) -> float` (normal truncated per documented semantics, uniform, triangular); `ALLOWED_PATHS: dict[str, Setter]` (allow-list, no `eval`/`getattr` on strings); `wilson_interval(k: int, n: int) -> tuple[float,float]`; `run_robustness(state, profile, catalog, *, n, seed) -> RobustnessResult` (per-sample seed from `{seed, i, param_id}`, works on a cloned state).

- [ ] **Step 1: Tests:** Wilson(80,100) ≈ (0.7112, 0.8666) ±0.0005; Wilson(0,100) lower = 0 and upper ≈ 0.0370, no NaN; Wilson(100,100) upper = 1; n=0 ⇒ validation error; same seed ⇒ identical samples/results; bounds respected for each distribution; path not in allow-list ⇒ rejected (Review Focus #1); input `MissionState` unchanged (deep-equal before/after); failure counts keys are constraint IDs; 250 samples < 2 s; n above cap clamped/`SIMULATION_LIMIT_EXCEEDED`; result includes N, seed, profile version, epistemic/aleatory labels and the "game-level proxy, not flight risk" statement.
- [ ] **Step 2–4:** implement; UI shows probability, interval, p10/median/p90, top failure causes, assumptions. Commit.

### Task 6.4: Science belief tracker + contracts for autonomy (FR-20, AC-18)

**Files:** `domain/science_belief/{bayesian_update,entropy,expected_information_gain}.py`, `data/scenarios/neo-rendezvous.events.json` (3 synthetic hypotheses, likelihood tables — all `gameplay-estimate`), `components/science-evidence/*`
**Interfaces:** `update_belief(belief, likelihood, outcome_id) -> BeliefState`; `entropy_bits(probs)`; `expected_information_gain(belief, instrument_likelihoods) -> float`.

- [ ] **Step 1: Tests:** uniform prior + likelihood [0.7,0.2,0.1] ⇒ posterior [0.7,0.2,0.1]; posterior sums to 1 (±1e-12); outcome more likely under H ⇒ H posterior rises vs others; all-zero marginal ⇒ validation error (not NaN); `entropy([0.5,0.5])==1.0`, with zero-probability term ignored; EIG ≥ −1e-12 and 0 for an uninformative instrument; update < 1 ms (3–8 hypotheses); hidden truth never in API payloads during run.
- [ ] **Step 2–4:** implement; UI shows prior → observation → posterior, likelihood explanation, "what next reduces entropy", downlinked-or-not flag, "conditional on scenario model" label. Commit. (Freeze `ObservationOpportunity`, `ContactWindow`, `AutonomyAction` contracts here for 6.5/6.6.)

### Task 6.5: Onboard autonomy + blackout (FR-21, AC-19)

**Files:** `domain/operations/{score_actions,plan_autonomy}.py`, simulation hook in `runner.py`, `components/mission-control/AuthorityBanner.tsx`
**Interfaces:** `score_actions(actions, belief, resources, weights) -> list[ScoredAction]` (utility = `w_s·value + w_i·EIG − w_e·E − w_d·D − w_r·risk − w_slew·slew`); `plan_autonomy(policy: Literal["conservative","science-first","resource-aware"], …) -> AutonomyDecision(decision_maker, candidates, selected, reason)`; `apply_ground_command(...)` raises `GroundCommandRejected` during blackout. Tie-break by action ID.

- [ ] **Step 1: Tests:** an action breaching battery reserve/storage/pointing/thermal never selected; during blackout ground command rejected and log `decision_maker=="onboard-policy"`; after contact, replanning allowed; same inputs ⇒ same choice; at most 10 candidates considered; log has belief input, candidate utilities, selected, reason; conservative skips low-confidence observation that science-first takes.
- [ ] **Step 2–4:** implement; UI: GROUND CONTROL vs ONBOARD AUTONOMY indicator, ground controls disabled in blackout with countdown, utility comparison table. Commit.

### Task 6.6: Science/downlink scheduler (FR-22, AC-20)

**Files:** `domain/operations/schedule_data_cycles.py`, `routes/missions.py` (`POST /api/mission/schedule`), `components/schedule/ScheduleBoard.tsx`
**Interfaces:** `schedule_data_cycles(opps, contacts, resources, policy) -> MissionSchedule(accepted, rejected: list[(id, reason_code)], cycles, buffer_timeline)`; greedy: sort by (priority, expected science, start, id); reject codes `INSTRUMENT_CONFLICT, ENERGY, POINTING, BUFFER_OVERFLOW_BEFORE_CONTACT, NO_CONTACT`.

- [ ] **Step 1: Tests:** buffer never exceeds capacity without explicit data-loss event; downlinked ≤ min(contact capacity, buffered); overlapping single-instrument opps not both accepted; **empty contacts list** ⇒ accepts only what fits buffer, rejects rest with `NO_CONTACT`/`BUFFER…`; deterministic; every accepted observation traces to a requirement; 50 opps/10 contacts < 100 ms.
- [ ] **Step 2–4:** implement; feed schedule into `runner.py`; UI timeline with observation/contact/buffer/power on one axis, labelled "greedy heuristic, not optimal". Commit.

### Task 6.7: Health monitor (FR-23, AC-21)

**Files:** `domain/health_monitor/{ewma,detect_anomalies}.py`, `components/mission-control/TelemetryResidual.tsx`
**Interfaces:** `ewma(residuals, lam) -> list[float]`; `detect_anomalies(samples, config: DetectorConfig(expected, warn, crit, persistence_k, hard_limit, lam)) -> list[Anomaly(channel, unit, observed, baseline, threshold, window, severity, subsystems, explanation)]`.

- [ ] **Step 1: Tests:** single spike below hard limit ⇒ no critical; k consecutive EWMA exceedances ⇒ warning; > crit or hard limit ⇒ critical; hysteresis clears only below lower threshold; persistent drift detected, noise-only series ⇒ none; deterministic; seeded false-positive teaching scenario explained; anomaly maps to a scenario event + recovery decision.
- [ ] **Step 2–4:** implement; UI shows raw, envelope, residual, EWMA, persistence count, threshold. Commit.

### Task 6.8: Mission Analyst (FR-24) — deterministic counterfactuals

**Files:** `domain/analyst/{recommend_mutations,explain_constraint}.py`, `routes/missions.py` (`POST /api/mission/recommend`), `components/review/Counterfactual.tsx`
**Interfaces:** `recommend(state, analysis, catalog, *, max_n=3) -> list[Recommendation(mutation, metric_before, metric_after, tradeoffs, confidence_label)]` by re-running the engine on single catalogue swaps; apply ⇒ new `design_revision`.

- [ ] **Step 1: Tests:** every number in a recommendation equals a re-computed engine value; recommendations contain only allow-listed mutation kinds (no free text instructions accepted); empty list (not error) when design already optimal; applying increments revision.
- [ ] **Step 2–4:** implement; replace Task 4.4 counterfactual stub. Commit.

### Task 6.9: Evidence Passport v2

**Files:** extend `domain/dossier/*`
- [ ] **Step 1: Tests (AC-22):** includes STM/MTM, Pareto position, robustness seed/N/assumptions, schedule/data cycles, anomalies, autonomy decisions, final science (collected vs returned), limitations; importing reproduces same nominal run. **Step 2–4** implement. Commit. **Gate G4.**

---

# Phase 7 — Polish, Scenarios, Release (M05, M19)

### Task 7.1: Remaining scenarios (P1/P2)
- [ ] Complete Lunar Polar Scout and Earth Observation templates + events (Earth orbit uses 2.6 two-body period; lunar uses scenario-preset trajectory, labelled); catalogue extras only if each has provenance; tests: each scenario analyses, simulates, replays deterministically; enable cards on landing. Commit.

### Task 7.2: 2D mission map first, then lazy 3D (M05)
- [ ] 2D schematic of trajectory/phase markers (labelled "illustrative geometry / scale"), driven by `trajectory` data only; 3D via `next/dynamic` with R3F, not in landing bundle (assert via bundle analysis that `three` absent from `/` chunk); reduced-motion respected; WebGL missing ⇒ 2D; accessible text equivalent. Commit.

### Task 7.3: Guided tutorial, concept cards, pre/post checks (F-021, LO-1…LO-7)
- [ ] Concept cards on first encounter of metrics (mass vs power vs energy; C3 vs ΔV; collected vs returned); optional prediction prompt; 3-question pre/post check stored locally only, no analytics; tests: completing first mission with hints, no blocking modals. Commit.

### Task 7.4: Accessibility, responsive, copy/attribution
- [ ] axe-core run in Playwright on all routes (0 serious violations); keyboard path for the full journey; contrast; mobile 375 px (brief + feasibility + decisions prioritised); `/about` with sources, credits, non-endorsement, fidelity tier explanations; no NASA logo. Commit.

### Task 7.5: Release QA & demo rehearsal (M19)
- [ ] Full Playwright journey (prod §14 demo route) in Chromium desktop + 375 px; offline mode run; fresh clone → `uv sync` / `pnpm install` / `check_all` green; golden drift fixtures for analysis + run; manual source audit of catalogue (every displayed number has provenance); coverage ≥ 90 % on core modules; seeded demo mission shipped as `data/missions/demo-saved.json`; backup screen recording; checklist from README §15 and prod §18 ticked. **Gate G6.**

---

## Decisions Needed / Inconsistencies in the Source Docs

| # | Issue | Default taken in this plan |
|---|---|---|
| D1 | `README` lists `domain/evidence`, architecture lists `domain/dossier`, M18 also references `domain/evidence` | Use `domain/dossier`; schemas in `schemas/evidence.py` |
| D2 | M12 puts autonomy in `domain/autonomy`; architecture §20 puts it in `domain/operations/plan_autonomy.py` | Follow architecture §20 (operations) |
| D3 | Policy names differ (conservative/balanced/science-seeking vs conservative/science-first/resource-aware) | Use architecture §19.5 names |
| D4 | `Uncertainty.distribution` includes `interval`; `DistributionSpec` does not; traceability node/edge enums differ (M09 vs architecture §19.1) | Architecture §19.x enums win; `interval` handled as epistemic uniform range |
| D5 | Docs say "decimal precision internally" but use `float` models | Use `float`; round only for display; document in CONTRACTS.md |
| D6 | JPL supported `signature.version` value | Verify when capturing fixture (Task 5.1) before hard-coding |
| D7 | Route notation `neo/[designation]` is Next-style | FastAPI path `/api/space-data/neo/{designation}` |
| D8 | Catalogue numeric values | Cannot be invented: each needs primary-source lookup (NASA SmallSat SoA 2026) or `gameplay-estimate` flag — human source-audit time must be budgeted in Task 1.4/7.5 |
| D9 | Who is the "integration owner"? | Single human owner of Tasks 0.x, 1.3, manifests/lockfiles |

## Self-Review

- **Spec coverage:** README milestones 0–5 → Phases 0–7; M01–M19 each mapped (M01→0.2/3.2, M02→3.3–3.5, M03/M04→4.4, M05→7.2, M06→1.1–1.3, M07→1.4–1.5, M08→2.x, M09→6.1, M10→6.2, M11→6.3, M12→6.4–6.5, M13→6.6, M14→4.1–4.2, M15→6.7, M16→3.1/4.3/5.3, M17→5.x, M18→4.5, M19→0.3/7.5); AC-01…AC-23 covered except AC-23 (LLM independence) which holds by omission — P2 LLM narration (FR-26) intentionally not planned; F-023 (Mode M), F-024–F-026 deferred per cut order.
- **Type consistency:** `analyze_mission`, `MissionAnalysis`, `MissionRun`, `RobustnessResult`, `ObservationOpportunity`, `ContactWindow` names are used identically across tasks; `design_revision` snake_case in Python / `designRevision` in JSON.
- **Proportion:** the plan specifies signatures, tests, known-answer values and constants, not function bodies.
