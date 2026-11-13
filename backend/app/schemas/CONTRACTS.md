# MISSIONFORGE Interface v1 — shared contracts (frozen)

Frozen by Task 1.3 (`feat(schemas): freeze Interface v1 (G1 part 1)`). From this commit on,
everything in `backend/app/schemas/` is **protected**: changes need approval from the
owner(s) below plus the integration owner (D9), an entry in the change log at the bottom,
and regenerated snapshots.

Freeze test: `backend/tests/contract/test_schema_freeze.py` compares
`model_json_schema(by_alias=True)` of every public model against
`backend/tests/contract/snapshots/<module>.json`. Regenerate after an approved change
(from `backend/`):

```bash
UPDATE_SNAPSHOTS=1 uv run python -m pytest tests/contract -q
# PowerShell: $env:UPDATE_SNAPSHOTS=1; uv run python -m pytest tests/contract -q
```

Then run `bash scripts/check_all.sh` (regenerates `openapi.json` / frontend types only if a
route exposes the changed model).

## Conventions (apply to every contract)

- All models derive from `ContractModel` (`api.py`): camelCase JSON aliases, snake_case
  accepted on input (`populate_by_name`), unknown fields rejected (`extra="forbid"`).
- Every float is `FiniteFloat` (strict, NaN/±inf rejected) or a constrained alias:
  `UnitFraction` = finite in [0, 1], `NonNegativeFloat` = finite ≥ 0 (`units.py`).
- Every int is `StrictInt`, every bool is `StrictBool` (no `"true"`/`1` coercion).
- No `Any` except `ApiError.details` (architecture §11.1). Free-form maps use
  `Scalar = StrictStr | StrictBool | StrictInt | FiniteFloat` (`units.py`).
- SI units internally; fractions are 0..1. Schedule/belief times are mission elapsed
  seconds; simulation `mission_day` is days.
- Schemas are a leaf layer: no module in `app/schemas/` imports `app.domain`, `app.api`,
  `app.services`, `app.integrations`, `app.infrastructure`, `app.main` or FastAPI
  (static AST test `test_schema_modules_do_not_import_outer_layers`).

## Contract list

| Contract(s) | Module | Owner / change approver |
|---|---|---|
| `ApiMeta`, `ApiError`, `ApiResult[T]`, `ContractModel`, `to_camel` | `app/schemas/api.py` | Backend/integration lead |
| `Fidelity`, `Unit`, `Provenance`, `Uncertainty`, `Quantity`, `FiniteFloat`, `UnitFraction`, `NonNegativeFloat`, `Scalar` | `app/schemas/units.py` | Python domain lead |
| `sanitize_title`, `MAX_TITLE_LENGTH` (helpers, not models) | `app/schemas/_text.py` | Domain lead |
| `Destination`, `TrajectorySelection` | `app/schemas/trajectory.py` | Data lead + domain lead |
| `MissionState`, `ScienceObjective`, `MeasurementRequirement`, `ComponentSelection`, `SpacecraftArchitecture`, `ObservationPlanItem`, `DownlinkPlanItem`, `OperationsPlan`, `MissionConstraints`, `ValidationIssue` | `app/schemas/mission.py` | Domain lead + integration lead |
| `FailureMode`, `CompatibilityRule`, `CatalogComponent` (`ComponentCategory`) | `app/schemas/catalog.py` | Data/domain lead |
| `SuggestedAction`, `ConstraintResult`, `BudgetAnalysis`, `ScienceAnalysis`, `ReliabilityAnalysis`, `ScoreDimension`, `ScoreBreakdown`, `MissionAnalysis` (`ConstraintStatus`, `Feasibility`, `ScoreDimensionId`) | `app/schemas/analysis.py` | Domain lead |
| `Phase`, `DecisionChoice`, `MissionEvent`, `TelemetrySample`, `DecisionRecord`, `ScienceOutcome`, `FinalReport`, `MissionRun`, `SimulationInput` (`EventType`, `EventSeverity`, `DecisionMaker`, `EventDecisionMaker`) | `app/schemas/simulation.py` | Simulation lead + integration lead |
| `ArchitectureNode`, `ArchitectureEdge` (`ArchitectureNodeKind`, `ArchitectureEdgeKind`), `OptimizationObjective`, `ArchitectureCandidate`, `TradeAlternative`, `TradeStudyResult`, `OptimizationResult` (`ObjectiveKey`, `Archetype`) | `app/schemas/optimization.py` | Algorithms lead |
| `DistributionSpec`, `UncertainParameter`, `UncertaintyProfile`, `MetricQuantiles`, `RobustnessResult` | `app/schemas/uncertainty.py` | Algorithms lead |
| `ScienceHypothesis`, `ObservationLikelihood`, `HypothesisProbability`, `ObservationRecord`, `BeliefState` | `app/schemas/science_belief.py` | Algorithms lead + product owner |
| `ObservationOpportunity`, `ContactWindow`, `ScheduledDataCycle`, `RejectedOpportunity`, `BufferPoint`, `MissionSchedule`, `AutonomyAction`, `ScoredAction`, `AutonomyDecision` (`RejectionReason`, `AutonomyPolicy`) | `app/schemas/operations.py` | Operations algorithms owner |
| `EvidenceRecord`, `MissionRunManifest`, `MissionPackageManifest`, `MissionPackage` | `app/schemas/evidence.py` | Product/data lead + integration lead |

## Decisions applied

- **D1** — Evidence/dossier domain code lives in `domain/dossier`; its schemas are in
  `schemas/evidence.py`.
- **D2** — Autonomy contracts (`AutonomyAction`, `ScoredAction`, `AutonomyDecision`) live
  in `schemas/operations.py` alongside scheduling (architecture §20), not a separate
  autonomy package.
- **D3** — Autonomy policies use architecture §19.5 names:
  `conservative | science-first | resource-aware`.
- **D4** — Architecture §19.x enums win over M09: `ArchitectureNodeKind` /
  `ArchitectureEdgeKind` are exactly §19.1. `Uncertainty.distribution == "interval"`
  (units.py) has no `DistributionSpec` counterpart; it is handled as an **epistemic
  `uniform`** range when converted into an `UncertainParameter`.
- **D5** — Docs mention "decimal precision"; all numeric fields are `float`
  (`FiniteFloat`). Rounding happens only for display, never in the engine.
- **R9** — (a) `sanitize_title` and `MAX_TITLE_LENGTH` moved to the leaf module
  `schemas/_text.py`; `schemas/mission.py` imports from there (and re-exports
  `MAX_TITLE_LENGTH`); `domain/mission/validation.py` re-exports `sanitize_title` for
  backward compatibility. This removes the schemas → domain import cycle.
  (b) `MeasurementRequirement.required` and `ComponentSelection.enabled` are now
  `StrictBool`; every bool added in Interface v1 is `StrictBool`.

## Deviations from the spec text (and why)

All deviations are additive or tighten validation; none rename a spec field.

### General
1. **Floats/ints/bools tightened** — spec `float`/`int`/`bool` became `FiniteFloat` (or
   `UnitFraction`/`NonNegativeFloat` where the quantity is a probability/fraction or a
   physically non-negative amount), `StrictInt`, `StrictBool`. Reason: NaN/inf must never
   enter or leave the engine; JSON imports must not coerce types (Review Focus #1, #4).
2. **`Any` removed** — `MissionEvent.trigger` is `dict[str, Scalar]`; `ArchitectureNode.attributes`
   is `dict[str, Scalar]` (spec `str | float | int | bool`, now strict + finite).

### catalog.py (§6.3)
3. Field set exactly as spec. `severity` is `StrictInt` 1..5; `base_probability` is
   `UnitFraction`; `is_illustrative` is `StrictBool`.

### analysis.py (§6.4)
4. `MissionAnalysis` adds `feasibility`, `mission_ready`, `score: ScoreBreakdown`,
   `top_drivers`, `assumptions` (module_breakdown §4.2B requires feasibility, score preview
   and top drivers; controller ruling).
5. New `ScoreBreakdown(total, dimensions)` and `ScoreDimension(id, weight, score,
   explanation)`; dimension ids are the five §7.11 dimensions.
6. **Invariant validator**: `mission_ready=True` is rejected when `feasibility ==
   "infeasible"` or any constraint has `status == "fail"` (global constraint: a failed hard
   constraint can never yield mission-ready).
7. `ScienceAnalysis` adds `collected_fraction` and `returned_fraction` (§7.10 requires
   collected-but-not-returned science to be reported separately).
   `weighted_objective_coverage` values are `UnitFraction`; `coverage_score` is ≥ 0 (0..100
   score per §7.10, not upper-bounded in the contract).
8. `ReliabilityAnalysis.nominal_reliability` is `UnitFraction`; `risk_index` ≥ 0.
9. `BudgetAnalysis` is exactly §6.4 (the optional `allocated_mass_kg` /
   `data_buffer_peak_bits` were **not** added — not needed yet).

### simulation.py (§9.2, §9.3, §9.6, module_breakdown §4.2C)
10. `Phase` is a closed `Literal` of ten phases (spec `phase: str`). §9.1 "extended mission
    or end-of-life" maps to `complete` / `terminated`; `downlink-return` covers §9.1 step 8.
11. `MissionEvent` adds `sequence` (stable ordering for replay/byte-identical output) and
    `decision_maker` (`ground | onboard-policy | player | system | None`, §19.5 log
    requirement). `choices` is `tuple[DecisionChoice, ...]` instead of `list[dict]`;
    `DecisionChoice(id, label, tradeoff, effects: dict[str, float])` covers §9.5 (actions,
    trade-off, predicted effect).
12. `TelemetrySample(channel, unit, mission_day, value, fidelity, phase)` — §9.3 asks for
    unit, timestamp (`mission_day`) and fidelity; `phase` added for phase-aware display.
    `channel` is a free `str` (channel ids are owned by the simulator; §9.3 lists the MVP
    set). Qualitative channels (thermal status, health flags) are encoded numerically
    (e.g. 0/1 flags with unit `%`), documented by the simulator.
13. `DecisionRecord(event_id, choice_id, decision_maker, mission_day, rationale)`;
    `decision_maker` is `ground | onboard-policy | player` (brief).
14. `ScienceOutcome(objective_id, collected_fraction, returned_fraction, status)` and
    `FinalReport(outcome, summary, score, root_causes, counterfactuals, limitations)` are new
    (spec names "science outcomes" and "final report" without fields).
15. `MissionRun` = brief fields + `experimental: StrictBool` + `phases: tuple[Phase, ...]`
    (§4.2C "phase transitions"). It is **frozen**: all simulation output models use
    `frozen=True` and collections are tuples (JSON: arrays), so a completed run cannot be
    mutated. Limitation: `dict` fields (`trigger`, `effects`) and the nested
    `ScoreBreakdown` (analysis.py, not frozen) remain technically mutable in Python; do not
    mutate them.
16. `SimulationInput` exactly §9.6; `monte_carlo_samples` ≥ 1 when present.

### optimization.py (§8.4, §19.1, §19.2)
17. `ArchitectureNode` / `ArchitectureEdge` / `OptimizationObjective` /
    `ArchitectureCandidate` exactly as §19.1/§19.2 (types tightened). Graph contracts live
    here because the brief's file list has no separate graph schema module.
18. `TradeStudyResult(base_analysis, alternatives: list[TradeAlternative(analysis,
    deltas)])` — not specified in the source docs; `deltas` are alternative − base, SI.
19. `OptimizationResult(seed, objectives, candidates, pareto_front_ids, archetypes,
    near_misses)` — `seed` and `objectives` are additions so a result records how its
    objective vectors were built and can be reproduced. `near_misses` is a list of
    candidate **ids** (the infeasible candidates are already in `candidates` with their
    constraint explanations), avoiding duplicated analyses.

### uncertainty.py (§19.3)
20. `RobustnessResult` adds `profile_version`, `assumptions`, `disclaimer`; new
    `UncertaintyProfile(id, version, parameters)`. Module_breakdown §4.1 calls this
    `RobustnessReport`; the §19.3 name `RobustnessResult` is used.
21. Validators: `DistributionSpec` requires `mean` + `std_dev > 0` (normal), `min < max`
    (uniform), `min <= mode <= max` with `min < max` (triangular); optional `min`/`max` on a
    normal are truncation bounds and must satisfy `min < max`. `feasibility_wilson_95` is an
    ordered pair of fractions; `failure_counts` ≥ 0. `MetricQuantiles.unit` stays `str` (some
    metrics, e.g. score, have no `Unit` literal).

### science_belief.py (§19.4)
22. Field sets exactly §19.4. Module_breakdown §4.1 names (`ScienceBeliefState`,
    `ObservationOutcome`) are superseded by §19.4 names (`BeliefState`, `ObservationRecord`).
23. `BeliefState` validator: hypothesis ids unique and probabilities sum to 1 (±1e-6) when
    non-empty. Probabilities/likelihoods are `UnitFraction`; `entropy_bits` ≥ 0.

### operations.py (§19.5, §19.6)
24. `ObservationOpportunity`, `ContactWindow`, `ScheduledDataCycle` exactly §19.6 field
    sets; `end >= start` validated; times are mission elapsed seconds.
25. New `MissionSchedule(accepted, rejected: list[RejectedOpportunity(id, reason_code)],
    cycles, buffer_timeline: list[BufferPoint(t, bits)])`, `AutonomyAction`,
    `ScoredAction`, `AutonomyDecision(decision_maker: ground | onboard-policy, policy,
    candidates, selected_action_id, reason)` — §19.5/§19.6 describe these without fields.

### evidence.py (module_breakdown §4.2D, M18, §19.9)
26. `EvidenceRecord` fields derived from the §4.2D bullet list: `id`, `subject_id`,
    `fidelity`, `source_title`, `source_url`, `source_version` (also API signature),
    `retrieved_at`, `published_at`, `unit`, `conversion_notes`, `assumptions`,
    `limitations`, `related_ids`.
27. `MissionRunManifest(schema_version, engine_version, catalog_version, scenario_version,
    event_set_id, seed, app_version)` (§19.9). Versions are plain `str` so mismatched
    imports remain representable and can be flagged "not identical replay".
28. `MissionPackage` per M18 but `exported_at` is `datetime` (spec `str`) and
    `package_schema_version` is `Literal["1.0"]` so packages from unknown versions are
    rejected at the boundary (migrations handle older versions before validation).
    M18 used plain `BaseModel`; these use `ContractModel` like every other contract.

## Change log

| Date | Change | Approved by |
|---|---|---|
| 2026-11-13 | Interface v1 frozen (Task 1.3) | integration owner (D9) |
