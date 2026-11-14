# MISSIONFORGE Interface v1 — shared contracts (frozen)

Frozen by Task 1.3 (`feat(schemas): freeze Interface v1 (G1 part 1)`, fix round 1 per
controller ruling R10). From then on everything in `backend/app/schemas/` is
**protected**: a change needs a controller ruling naming the change, an entry in the
change log at the bottom, and deliberately regenerated snapshots.

Freeze test: `backend/tests/contract/test_schema_freeze.py` compares
`model_json_schema(by_alias=True)` of every public model against
`backend/tests/contract/snapshots/<module>.json`. Regenerate after a ruled change
(from `backend/`):

```bash
UPDATE_SNAPSHOTS=1 uv run python -m pytest tests/contract -q
# PowerShell: $env:UPDATE_SNAPSHOTS=1; uv run python -m pytest tests/contract -q
```

The test refuses to rewrite snapshots when the `CI` environment variable is set, so a
leaked `UPDATE_SNAPSHOTS` cannot hide drift in CI. Afterwards run `bash scripts/check_all.sh`,
which regenerates `openapi.json` / frontend types only when a route exposes the changed model.

## Conventions (apply to every contract)

- All models derive from `ContractModel` (`api.py`): camelCase JSON aliases, snake_case
  accepted on input (`populate_by_name`), unknown fields rejected (`extra="forbid"`).
- Every float is `FiniteFloat` (strict, NaN/±inf rejected) or a constrained alias:
  `UnitFraction` = finite in [0, 1], `NonNegativeFloat` = finite ≥ 0 (`units.py`).
- Every int is `StrictInt` and every bool is `StrictBool`, so `"true"` and `1` are not
  coerced.
- No `Any` except `ApiError.details` (architecture §11.1). Free-form maps use
  `Scalar = StrictStr | StrictBool | StrictInt | FiniteFloat` (`units.py`).
- SI units internally; fractions are 0..1 and use unit `"fraction"` (R10). `"%"` is kept
  for display-oriented values only. Schedule/belief times are mission elapsed seconds;
  simulation and health-monitor times are mission days.
- **Immutability** (`_frozen.py`): `FrozenContract` = frozen (assignment raises
  `ValidationError`) + `revalidate_instances="always"`, so passing an existing instance
  stores a validated copy rather than an alias. Frozen models use `tuple[...]` for
  collections and `FrozenMap[V]` for maps. `FrozenMap` is an immutable, hashable
  `Mapping[str, V]` that validates like `dict[str, V]` (NaN rejected) and has the same JSON
  schema. Tuples and `FrozenMap` change only Python behaviour; the JSON schemas are
  identical to `list`/`dict`, which the snapshots confirm. Every model reachable from
  `MissionRun` is frozen, so a run is deeply immutable and hashable.
- Schemas are a leaf layer. No module in `app/schemas/` imports `app.domain`, `app.api`,
  `app.services`, `app.integrations`, `app.infrastructure`, `app.main` or FastAPI, and none
  uses a relative import. The static AST test `test_schema_modules_do_not_import_outer_layers`
  enforces this.

## Contract list

| Contract(s) | Module | Owner |
|---|---|---|
| `ApiMeta`, `ApiError`, `ApiResult[T]`, `ContractModel`, `to_camel` | `app/schemas/api.py` | Backend/integration lead |
| `FrozenContract`, `FrozenMap` (building blocks) | `app/schemas/_frozen.py` | Backend/integration lead |
| `sanitize_title`, `MAX_TITLE_LENGTH` (helpers) | `app/schemas/_text.py` | Domain lead |
| `Fidelity`, `Unit`, `Provenance`*, `Uncertainty`*, `Quantity`*, `FiniteFloat`, `UnitFraction`, `NonNegativeFloat`, `Scalar` | `app/schemas/units.py` | Python domain lead |
| `Destination`*, `TrajectorySelection`* | `app/schemas/trajectory.py` | Data lead + domain lead |
| `MissionState`* and parts* (`ScienceObjective`, `MeasurementRequirement`, `ComponentSelection`, `SpacecraftArchitecture`, `ObservationPlanItem`, `DownlinkPlanItem`, `OperationsPlan`, `MissionConstraints`), `ValidationIssue` | `app/schemas/mission.py` | Domain lead + integration lead |
| `FailureMode`, `CompatibilityRule`, `CatalogComponent` (`ComponentCategory`) | `app/schemas/catalog.py` | Data/domain lead |
| `SuggestedAction`, `ConstraintResult`, `BudgetAnalysis`, `ScienceAnalysis`, `ReliabilityAnalysis`, `ScoreDimension`*, `ScoreBreakdown`*, `MissionAnalysis` | `app/schemas/analysis.py` | Domain lead |
| `Phase`, `DecisionChoice`*, `MissionEvent`*, `TelemetrySample`*, `DecisionRecord`*, `ScienceOutcome`*, `PhaseTransition`*, `FinalReport`*, `MissionRunManifest`*, `MissionRun`*, `SimulationInput` | `app/schemas/simulation.py` | Simulation lead + integration lead |
| `ArchitectureNode`, `ArchitectureEdge`, `ArchitectureGraph`, `MetricChange`, `ImpactReport`, `OptimizationObjective`, `ArchitectureCandidate`, `TradeAlternative`, `TradeStudyResult`, `OptimizationResult` | `app/schemas/optimization.py` | Algorithms lead |
| `DistributionSpec`, `UncertainParameter`, `UncertaintyProfile`, `MetricQuantiles`, `RobustnessResult` | `app/schemas/uncertainty.py` | Algorithms lead |
| `ScienceHypothesis`, `ObservationLikelihood`, `HypothesisProbability`*, `ObservationRecord`*, `BeliefState`* | `app/schemas/science_belief.py` | Algorithms lead + product owner |
| `ObservationOpportunity`, `ContactWindow`, `ScheduledDataCycle`, `RejectedOpportunity`, `BufferPoint`, `MissionSchedule`, `AutonomyAction`, `ScoredAction`*, `AutonomyDecision`* | `app/schemas/operations.py` | Operations algorithms owner |
| `DesignMutation`, `Recommendation` | `app/schemas/analyst.py` | Domain lead |
| `DetectorConfig`, `Anomaly` | `app/schemas/health.py` | Simulation lead |
| `EvidenceRecord`, `MissionRunManifest` (re-export), `MissionPackageManifest`, `MissionPackage` | `app/schemas/evidence.py` | Product/data lead + integration lead |

`*` marks frozen models (`FrozenContract`).

## Decisions applied

- **D1**: Evidence/dossier domain code lives in `domain/dossier`, and its schemas are in
  `schemas/evidence.py`.
- **D2**: Autonomy contracts live in `schemas/operations.py` (architecture §20).
- **D3**: Autonomy policies use the architecture §19.5 names
  `conservative | science-first | resource-aware`.
- **D4**: Architecture §19.x enums win over M09, so `ArchitectureNodeKind` and
  `ArchitectureEdgeKind` are exactly as in §19.1. `Uncertainty.distribution == "interval"`
  has no `DistributionSpec` counterpart and is handled as an **epistemic `uniform`** range.
- **D5**: All numeric fields are `float` (`FiniteFloat`). Rounding happens only for display.
- **R9**: (a) `sanitize_title`/`MAX_TITLE_LENGTH` moved to the leaf module `schemas/_text.py`.
  `schemas/mission.py` imports them from there, and `domain/mission/validation.py`
  re-exports `sanitize_title`, which removes the schemas → domain import.
  (b) `MeasurementRequirement.required`, `ComponentSelection.enabled` and every new bool
  are `StrictBool`.
- **R10** (controller ruling, fix round 1; freeze-time shape decisions):
  1. MissionRun carries `input_snapshot` and `manifest` so it can be replayed.
  2. Everything reachable from MissionRun is deeply immutable.
  3. `AutonomyDecision.belief` and `MissionRun.autonomy_log`.
  4. Feasibility ⇔ failed-constraint consistency.
  5. `SimulationInput.experimental`.
  6. Unit `"fraction"`.
  7. Rejection reason `THERMAL` and schedule data-loss fields.
  8. `FinalReport.realized_risks` and `MissionRun.phase_transitions`.
  9. Cross-reference validators.
  10. Graph, impact, recommendation and health payload contracts.
  11. Snapshot CI guard.
  12. Wording: no human approval occurred; approvals are controller rulings.

## Deviations from the spec text (and why)

### General
1. **Types tightened**. Spec `float`/`int`/`bool` became `FiniteFloat` (or
   `UnitFraction`/`NonNegativeFloat`), `StrictInt` and `StrictBool`. This keeps NaN/inf out
   and stops JSON imports from coercing types (Review Focus #1, #4).
2. **`Any` removed**. `MissionEvent.trigger` is `FrozenMap[Scalar]` and
   `ArchitectureNode.attributes` is `dict[str, Scalar]`.
3. **Immutability (R10 #2)**. The following models are frozen with tuple collections:
   - `MissionState` and its parts, `Quantity`, `Provenance`, `Uncertainty`;
   - `Destination`, `TrajectorySelection`;
   - `ScoreBreakdown`, `ScoreDimension`;
   - all simulation output models;
   - `BeliefState`, `HypothesisProbability`, `ObservationRecord`;
   - `AutonomyDecision`, `ScoredAction`.

   `MissionState.science_objectives`, `.architecture.instrument_ids`,
   `.operations.observation_plan`/`downlink_plan`,
   `ScienceObjective.required_measurements` and `Provenance.assumptions` are now tuples
   in Python, and `ComponentSelection.overrides` is a `FrozenMap`. This is a Python-side
   behaviour change; the JSON shape is unchanged. MissionState stays the editable source of
   truth: an edit produces a new instance (`model_copy(update=...)` or re-validation), and
   `design_revision` is bumped as before.

### catalog.py (§6.3)
4. Fields are exactly as in the spec, with types tightened (`severity` 1..5,
   `base_probability` a fraction).

### analysis.py (§6.4, §7.10, §7.11)
5. `MissionAnalysis` adds `feasibility`, `mission_ready`, `score: ScoreBreakdown`,
   `top_drivers` and `assumptions` (module_breakdown §4.2B).
6. **Hard-feasibility invariant (R10 #4)**. A constraint with status `"fail"` is a hard
   failure; soft issues use `"warning"`. Validation enforces:
   - feasibility is `"infeasible"` **if and only if** at least one constraint failed, so
     `feasible`+fail, `marginal`+fail and `infeasible`+no-fail are all rejected;
   - `mission_ready=True` is rejected when the design is infeasible.
7. New `ScoreBreakdown(total, dimensions: tuple[ScoreDimension, ...])`. It must contain
   each of the five §7.11 dimension ids exactly once (R10 #9).
8. `ScienceAnalysis` adds `collected_fraction` and `returned_fraction` (§7.10).
   `coverage_score` is ≥ 0 (0..100).
9. `BudgetAnalysis` is exactly as in §6.4. The optional extra fields were not added.

### simulation.py (§9, §19.5, §19.9, module_breakdown §4.2C)
10. `Phase` is a closed Literal of ten phases (the spec has `phase: str`).
11. `MissionEvent` adds `sequence` and `decision_maker`
    (`ground | onboard-policy | player | system | None`). `choices` is
    `tuple[DecisionChoice(id, label, tradeoff, effects: FrozenMap[float])]` instead of
    `list[dict]`.
12. `TelemetrySample(channel, unit, mission_day, value, fidelity, phase)`. `channel` is a
    free `str` whose ids are owned by the simulator. 0..1 channels (state of charge,
    propellant fraction, health flags as 0/1) use unit **`"fraction"`**, not `"%"` (R10 #6).
13. `DecisionRecord.decision_maker` is `ground | onboard-policy | player`.
    *Usage note (Task 4.2, no schema change):* `DecisionChoice.effects` keys are the
    simulator's effects vocabulary (`app.domain.simulation.anomalies.EFFECT_KEYS`):
    `science_time_lost_days`, `link_outage_days`, `downlink_rate_factor`,
    `duty_cycle_factor`, `buffer_loss_fraction`, `soc_delta`, `propellant_delta` (telemetry-only),
    `terminate` (float values).
    A default choice made without the player is recorded with `decision_maker = "ground"`
    and rationale `"default (no player choice)"`; the event shows `"system"`. Anomaly and
    scenario events use declared ids `anomaly-<id>` / `scenario-<id>` as decision keys.
14. `ScienceOutcome` is new. `FinalReport(outcome, summary, score, realized_risks,
    root_causes, counterfactuals, limitations)` adds `realized_risks` (§9.6 output, R10 #8).
15. `MissionRun` fields:
    - the brief's fields, plus `experimental` and `phases`;
    - **`input_snapshot: MissionState`** and **`manifest: MissionRunManifest`** (R10 #1);
    - `phase_transitions: tuple[PhaseTransition(phase, mission_day)]` (§4.2C, R10 #8),
      ordered by day;
    - `autonomy_log: tuple[AutonomyDecision, ...] = ()` (§19.5, R10 #3).

    Validators require:
    - `input_snapshot.mission_id/design_revision` equal the run's values;
    - the manifest seed, engine/catalogue versions and event set match the run;
    - `manifest.schema_version` equals the snapshot's `schema_version`.
16. `MissionRunManifest` is **defined in simulation.py** because MissionRun embeds it, and
    defining it in evidence.py would create an import cycle. `app.schemas.evidence`
    re-exports the same class. Its versions are plain `str` so a mismatched import can be
    flagged "not identical replay".
17. `SimulationInput` is exactly as in §9.6, plus `experimental: StrictBool = False`
    (R10 #5). `monte_carlo_samples` must be ≥ 1.

### optimization.py (§8.4, §19.1, §19.2)
18. `ArchitectureNode`, `ArchitectureEdge`, `OptimizationObjective` and
    `ArchitectureCandidate` are exactly as in §19.1/§19.2. The graph contracts live here
    because no separate graph schema module exists.
19. New `ArchitectureGraph(nodes, edges)`: node ids are unique and every edge references a
    known node. New `ImpactReport(changed_metrics: list[MetricChange(metric, before, after,
    unit)], newly_violated, improved, affected_objectives)` covers §19.1 behaviour 7; the
    last three are id lists.
20. `TradeStudyResult(base_analysis, alternatives: list[TradeAlternative(analysis,
    deltas)])` is not specified in the source docs.
21. `OptimizationResult(seed, objectives, candidates, pareto_front_ids, archetypes,
    near_misses)`:
    - `seed` and `objectives` are additions;
    - `near_misses` holds candidate ids;
    - the validator checks that front, archetype and near-miss ids are all candidate ids
      and that the front and near-miss sets do not overlap (R10 #9).

### uncertainty.py (§19.3)
22. `RobustnessResult` adds `profile_version`, `assumptions` and `disclaimer`. New
    `UncertaintyProfile`. The §19.3 name `RobustnessResult` is used rather than
    "RobustnessReport" (§4.1).
23. Validators: distribution parameters must suit the kind, and the Wilson pair must be
    ordered fractions. `MetricQuantiles.unit` stays `str`.

### science_belief.py (§19.4)
24. Field sets are exactly as in §19.4, with the §19.4 names. `BeliefState` requires unique
    hypothesis ids and probabilities that sum to 1 (±1e-6) when non-empty.

### operations.py (§19.5, §19.6)
25. `ObservationOpportunity`, `ContactWindow` and `ScheduledDataCycle` are exactly as in
    §19.6, with `end >= start` validated.
26. `MissionSchedule(accepted, rejected: list[RejectedOpportunity(id, reason_code)],
    cycles, buffer_timeline, data_loss_risk_accepted = False, data_lost_bits = 0)`. The
    reason codes now include `THERMAL`. Validators require that accepted ∩ rejected = ∅ and
    that `data_lost_bits > 0` only when `data_loss_risk_accepted` (§19.6 step 5; R10 #7, #9).
27. `AutonomyDecision(decision_maker: ground | onboard-policy, policy, belief:
    BeliefState, candidates, selected_action_id, reason)`. `belief` is the input belief
    required by §19.5 (R10 #3).

### analyst.py (§19.8), new module
28. `Recommendation(id, mutation: DesignMutation, metric_before, metric_after, tradeoffs,
    confidence_label, source_refs, explanation)`. `DesignMutation(kind:
    swap-component | add-instrument | remove-instrument | change-operations, target,
    from_value, to_value, description)`. `confidence_label` is `high | medium | low`.
    `id` and `explanation` were added because §19.8 asks for a plain-language explanation.

### health.py (§19.7), new module
29. `DetectorConfig(channel, unit, expected, warn, crit, persistence_k, hard_limit, lam,
    rationale)` with `warn <= crit`, `persistence_k ≥ 1` and `0 < lam ≤ 1`. `expected` is
    a constant nominal value; a time-varying envelope would need a later ruling.
    `Anomaly(channel, unit, observed, baseline, threshold, window_start, window_end,
    severity: warning | critical, subsystems, explanation)` requires an ordered window in
    mission days.

### evidence.py (module_breakdown §4.2D, M18, §19.9)
30. `EvidenceRecord` fields are derived from the §4.2D bullet list (`subject_id`,
    `source_*`, `unit`, `conversion_notes`, `assumptions`, `limitations`, `related_ids`).
31. `MissionPackage` follows M18, with these differences:
    - `exported_at` is a `datetime`;
    - `package_schema_version` is `Literal["1.0"]`;
    - it uses `ContractModel`;
    - a validator requires every run's `mission_id` to match the packaged mission.

    Each run carries its own `input_snapshot`, so runs of older design revisions replay
    even after `mission` has moved on (R10 #1).

## Change log

| Date | Change | Basis |
|---|---|---|
| 2026-11-13 | Interface v1 frozen (Task 1.3) | controller rulings D1–D9, R9 |
| 2026-11-13 | Fix round 1: replayable immutable runs, autonomy belief, feasibility invariants, `fraction` unit, schedule data loss, phase transitions, cross-reference validators, graph/impact/analyst/health payloads, CI snapshot guard | controller ruling R10 |

## Templates (Task 1.5)

`app/schemas/templates.py` adds `ScenarioTemplate` / `TemplateMissionState` (new file; no existing contract changed). `TemplateMissionState` is MissionState without missionId, createdAt, updatedAt, randomSeed.

## Analysis engine notes (Task 2.8, documentation only; no schema change)

`analyze_mission` (`app/domain/analysis/orchestrator.py`) fills `MissionAnalysis` as follows.
Consumers must read these rules before interpreting the plain-float fields.

- **Failure path.** A design problem never raises. An unknown catalogue id, a missing or
  invalid catalogue parameter, invalid model input, or a contract `ValidationError` raised
  inside the engine produces a valid, infeasible, not-mission-ready `MissionAnalysis`. That
  result contains exactly one constraint with id `catalog-item-not-found` or
  `model-input-invalid`, and its explanation names the error code and field. On this path:
  - every budget `Quantity` is 0 with provenance fidelity `not-modelled`;
  - the bare-float margins (`massMarginFraction`, `energyMarginFraction`,
    `dataMarginFraction`, `deltaVMarginKmPerS`), the science fractions and scores, and
    `reliability.nominalReliability` / `riskIndex` are **placeholders (0), not results**.

  Consumers (API route, UI, dossier) must branch on those two constraint ids rather than
  read the numbers. The route layer may map `catalog-item-not-found` to the API error
  `CATALOG_ITEM_NOT_FOUND`.
- **Undefined margins on the happy path are 0.0.** The bare-float fields
  `massMarginFraction` (no launch limit), `energyMarginFraction` (no energy consumed) and
  `dataMarginFraction` (no data generated) are set to `0.0` when the quantity is
  undefined. The matching constraint (`mass-launch-limit`, `energy-closure`, `data-return`)
  is `not-modelled` in that case, so use the constraint status to tell "undefined" apart
  from "exactly zero margin".
- `dataMarginFraction` = total downlink capacity / generated − 1. This is the same measure
  as the `data-return` constraint, and it differs from the ledger's
  (downlinked − generated) / generated.

## Import and replay (Task 4.5)

- `POST /api/mission/import` takes the raw `MissionPackage` JSON as the body (limit 4 MiB, `max_import_bytes`;
  the default 256 KiB applies elsewhere). It rejects non-standard JSON (`NaN`, `Infinity`), an unsupported
  `packageSchemaVersion` / mission `schemaVersion` (never reinterpreted), more than 20 runs, duplicate run ids,
  run/mission mismatches and unknown catalogue components. Titles are sanitised by the schema. Nothing is stored.
- On success the response carries the validated package (`latestAnalysis` recomputed here) plus one
  `{runId, status, mismatches, analysis}` per run. `status` compares the run manifest (engine, catalogue,
  scenario, schema versions, event-set availability) with this server; `analysis` is the snapshot re-analysed by
  the current engine (derived, may differ from the recorded run when versions differ).
- `POST /api/mission/replay` re-runs `run.inputSnapshot` with its seed, event set and recorded player decisions.
  `identical` is true only after comparing the re-run to the recorded run (canonical JSON, numbers by value so a
  JS round trip's `275` equals `275.0`). A version difference returns `version-mismatch` without re-running.
  `manifest.appVersion` is a metadata stamp and does not make a run non-identical.
