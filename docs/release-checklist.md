# MISSIONFORGE release checklist (Task 7.5, Gate G6)

Status as of 2026-11-14. Ticked items have automated evidence in the repository; open items
need a person, or Phase 5 (JPL adapter), which is not built yet.

Commands (this machine blocks some `.exe` shims; see the project notes):

```bash
bash scripts/check_all.sh
cd frontend && PW_CHANNEL=chrome corepack pnpm@10.18.3 test:e2e
cd backend && uv run python -m pytest -q --cov=app
```

## README section 15: quality gates before submission

- [x] Clean `uv sync` in `backend/` and `pnpm install` in `frontend/` succeed from a fresh clone, and `scripts/check_all.sh` passes there (verified 2026-11-14 on a local clone; this check found that `typecheck` needed `next typegen` first).
- [x] Lint, typecheck, tests and build pass (`scripts/check_all.sh`: ruff, mypy, pytest, catalogue validator, API-type freshness, eslint, tsc, next build).
- [x] Core Playwright flow passes: `tests/e2e/demo-journey.spec.ts` runs the demo route at 1280 and 375 px; the whole suite is green.
- [x] No browser-side JPL requests: the frontend calls only the MISSIONFORGE API; JPL links in the passport are plain links checked server-side (R36).
- [ ] JPL version check, serialisation, cache and fallback verified: **Phase 5 not built.**
- [x] No unlabelled numerical assumptions: every catalogue value carries a fidelity label and provenance (catalogue validator); engine assumptions are listed per analysis and run. All catalogue values are gameplay estimates (R3) until the human source audit below.
- [x] No failed constraint hidden behind the overall score: hard constraints gate launch; failed constraints are shown separately from the score (AC tests in `architect.spec.ts`).
- [x] Same seeded mission produces the same result: golden analysis and run fixtures, replay tests, `test_all_scenarios.py`, demo-package drift test.
- [ ] Works without JPL network access: **true today because nothing calls JPL**; re-check once Phase 5 adds the live adapter and its offline snapshot.
- [x] Mobile layout verified at 375 px: no horizontal overflow on brief, architect, control and review; axe at 375 px.
- [x] WebGL fallback: there is no WebGL view (3D was cut per the cut order); the 2D mission map is the only map.
- [x] Credits and non-endorsement statement visible: footer on every page and `/about` (credits, sources, fidelity tiers, non-endorsement, no NASA/JPL logos).

## prod section 18: release checklist

### Product

- [x] Scenario brief tells a coherent science story (all three scenarios playable, Task 7.1).
- [x] Science objectives trace to measurements and instruments (traceability table, STM/MTM, graph).
- [x] Design page shows coupled budgets (live analysis; demo journey asserts a coupled mass change).
- [x] Hard constraint status is unmistakable (icon + word badges, launch gate, axe-checked contrast).
- [x] Mission simulation has meaningful operator decisions (>= 2 per scenario, blackout authority shown).
- [x] Post-mission report explains success / failure (review: root causes, counterfactuals, analyst, autonomy, health monitor).

### Engineering

- [x] Backend type / lint checks and frontend TypeScript checks pass.
- [x] Lint, unit, contract, integration and build checks pass.
- [x] Engineering equations have independent test vectors (known-answer tests in `tests/unit/analysis`).
- [ ] JPL adapter: server-side request, serial queue, cache, User-Agent, version check: **Phase 5.**
- [x] No direct client-to-JPL fetch.
- [ ] Offline snapshot path works: the seeded demo package (`data/demo/demo-saved.json`, "Load saved demo mission") works offline; the **JPL offline snapshot is Phase 5**.
- [x] Reproducibility check passes (replay, golden fixtures, demo drift test).

### Trust and communication

- [ ] Every spec and number has provenance or an explicit gameplay-estimate label: **labels are complete**; the **manual source audit** of the catalogue against primary tables (NASA SmallSat SoA 2026) still needs a person (decision D8 / ruling R3).
- [x] NASA / JPL sources are attributed (`/about`, passport sources).
- [x] App says it is an independent educational prototype.
- [x] No flight-readiness or mission-certification claim (limitations in every run and passport).
- [x] Data limitations are visible in the report.

### Demo

- [x] Fresh start works (fresh-clone check; landing-to-review journey).
- [x] One successful run rehearsed (automated: demo journey, saved demo mission "success").
- [x] One failed / recovered run rehearsed (automated: failing link repaired before launch; experimental and terminated runs covered in `mission-control.spec.ts`).
- [ ] Network-offline path rehearsed **on the judging laptop**: needs a person.
- [x] 2D fallback: the 2D map is the only map.
- [x] Dossier export works (Passport v2 JSON + HTML).
- [ ] Backup 60-second screen recording: needs a person.
- [ ] Full rehearsal on the exact judging laptop / browser: needs a person.

## Coverage (2026-11-14)

Backend: 98% of `app/` overall; every core domain module (analysis, simulation,
operations, health monitor, uncertainty, optimisation, architecture graph, science belief,
dossier, catalogue) is at or above 90%.
