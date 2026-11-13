"""Interface v1 contract freeze.

Snapshots of `model_json_schema(by_alias=True)` for every public contract model live in
tests/contract/snapshots/<module>.json. A schema change fails this test on purpose:
shared schemas are protected (see app/schemas/CONTRACTS.md). To accept an intentional,
approved change, regenerate from backend/:

    UPDATE_SNAPSHOTS=1 uv run python -m pytest tests/contract -q

(PowerShell: $env:UPDATE_SNAPSHOTS=1; uv run python -m pytest tests/contract -q)
"""

import ast
import importlib
import inspect
import json
import math
import os
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from app.schemas.api import ContractModel

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "app" / "schemas"
SNAPSHOT_DIR = Path(__file__).resolve().parent / "snapshots"
SCHEMA_MODULES = (
    "api",
    "units",
    "trajectory",
    "mission",
    "catalog",
    "analysis",
    "simulation",
    "optimization",
    "uncertainty",
    "science_belief",
    "operations",
    "evidence",
    "analyst",
    "health",
)
REGEN_HINT = "UPDATE_SNAPSHOTS=1 uv run python -m pytest tests/contract -q"


def _module(name: str) -> ModuleType:
    return importlib.import_module(f"app.schemas.{name}")


def _models(mod: ModuleType) -> dict[str, type[BaseModel]]:
    found: dict[str, type[BaseModel]] = {}
    for name, obj in inspect.getmembers(mod, inspect.isclass):
        if not issubclass(obj, BaseModel) or obj.__module__ != mod.__name__:
            continue
        if obj is ContractModel or name.startswith("_"):
            continue
        if obj.__pydantic_generic_metadata__["parameters"]:  # unparametrised generic
            continue
        found[name] = obj
    return found


def _all_contracts() -> dict[str, type[BaseModel]]:
    out: dict[str, type[BaseModel]] = {}
    for m in SCHEMA_MODULES:
        for name, model in _models(_module(m)).items():
            out[f"{m}.{name}"] = model
    return out


# --- coverage of the builder registry ---------------------------------------------------


def test_every_contract_has_a_builder(builders: dict[str, Callable[[], BaseModel]]) -> None:
    missing = sorted(set(_all_contracts()) - set(builders))
    assert not missing, f"add realistic builders in tests/contract/conftest.py for: {missing}"


def test_builders_produce_the_named_model(
    contract_name: str, builders: dict[str, Callable[[], BaseModel]]
) -> None:
    assert type(builders[contract_name]()) is _all_contracts()[contract_name]


# --- JSON round trip ---------------------------------------------------------------------


def test_json_round_trip(contract_name: str, builders: dict[str, Callable[[], BaseModel]]) -> None:
    instance = builders[contract_name]()
    model = type(instance)
    text = instance.model_dump_json(by_alias=True)
    again = model.model_validate_json(text)
    assert again == instance
    assert again.model_dump_json(by_alias=True) == text
    # snake_case python dump must also be accepted (populate_by_name)
    assert model.model_validate(instance.model_dump()) == instance


def test_serialised_output_uses_camel_case(builders: dict[str, Callable[[], BaseModel]]) -> None:
    data = builders["analysis.MissionAnalysis"]().model_dump(mode="json", by_alias=True)
    assert "missionReady" in data and "topDrivers" in data
    assert "collectedFraction" in data["science"]


# --- snapshot freeze ---------------------------------------------------------------------


@pytest.mark.parametrize("module_name", SCHEMA_MODULES)
def test_schema_snapshot(module_name: str) -> None:
    current = {
        name: model.model_json_schema(by_alias=True)
        for name, model in sorted(_models(_module(module_name)).items())
    }
    path = SNAPSHOT_DIR / f"{module_name}.json"
    rendered = json.dumps(current, indent=2, sort_keys=True) + "\n"
    if os.environ.get("UPDATE_SNAPSHOTS") == "1":
        if os.environ.get("CI"):
            pytest.fail("UPDATE_SNAPSHOTS is not allowed in CI; snapshots must be committed")
        SNAPSHOT_DIR.mkdir(exist_ok=True)
        path.write_text(rendered, encoding="utf-8", newline="\n")
    assert path.exists(), f"missing snapshot {path.name}; run: {REGEN_HINT}"
    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored == current, (
        f"schema drift in app/schemas/{module_name}.py. Shared schemas are frozen: get "
        f"approval, record it in CONTRACTS.md, then run: {REGEN_HINT}"
    )


def test_mission_analysis_field_names_are_frozen() -> None:
    from app.schemas.analysis import MissionAnalysis

    props = set(MissionAnalysis.model_json_schema(by_alias=True)["properties"])
    assert props == {
        "missionId", "designRevision", "engineVersion", "catalogVersion", "calculatedAt",
        "budgets", "science", "reliability", "constraints", "feasibility", "missionReady",
        "score", "topDrivers", "assumptions",
    }  # fmt: skip


# --- immutability ------------------------------------------------------------------------


def test_mission_run_is_immutable(builders: dict[str, Callable[[], BaseModel]]) -> None:
    run = builders["simulation.MissionRun"]()
    with pytest.raises(ValidationError):
        run.seed = 7
    with pytest.raises(ValidationError):
        run.events[0].title = "rewritten"
    with pytest.raises(AttributeError):
        run.events.append(run.events[0])  # type: ignore[attr-defined]
    with pytest.raises(ValidationError):
        run.final_report.summary = "rewritten"
    with pytest.raises(ValidationError):
        run.input_snapshot.title = "rewritten"
    with pytest.raises(ValidationError):
        run.manifest.seed = 1


def test_mission_run_nested_score_cannot_change(
    builders: dict[str, Callable[[], BaseModel]],
) -> None:
    run = builders["simulation.MissionRun"]()
    with pytest.raises(ValidationError):
        run.final_report.score.total = 100.0
    with pytest.raises(ValidationError):
        run.final_report.score.dimensions[0].score = 100.0
    with pytest.raises(AttributeError):
        run.final_report.score.dimensions.append(  # type: ignore[attr-defined]
            run.final_report.score.dimensions[0]
        )


def test_validation_copies_instead_of_aliasing(
    builders: dict[str, Callable[[], BaseModel]],
) -> None:
    from app.schemas.simulation import FinalReport

    sb = builders["analysis.ScoreBreakdown"]()
    report = FinalReport(
        outcome="success",
        summary="s",
        score=sb,  # type: ignore[arg-type]
        realized_risks=[],  # type: ignore[arg-type]
        root_causes=[],  # type: ignore[arg-type]
        counterfactuals=[],  # type: ignore[arg-type]
        limitations=[],  # type: ignore[arg-type]
    )
    assert report.score == sb
    assert report.score is not sb


def test_trigger_and_effects_maps_are_immutable(
    builders: dict[str, Callable[[], BaseModel]],
) -> None:
    run = builders["simulation.MissionRun"]()
    event = run.events[0]
    with pytest.raises(TypeError):
        event.trigger["threshold"] = math.nan  # type: ignore[index]
    with pytest.raises(TypeError):
        event.choices[0].effects["science_days"] = 0.0  # type: ignore[index]
    assert '"threshold":0.3' in event.model_dump_json()


def test_mission_run_is_hashable(builders: dict[str, Callable[[], BaseModel]]) -> None:
    run = builders["simulation.MissionRun"]()
    again = type(run).model_validate_json(run.model_dump_json())
    assert hash(run.final_report) == hash(again.final_report)
    assert hash(run) == hash(again)


# --- non-finite rejection ----------------------------------------------------------------

NAN_CASES = [
    ("analysis.MissionAnalysis", ("budgets", "mass_margin_fraction")),
    ("analysis.MissionAnalysis", ("score", "total")),
    ("analysis.ScienceAnalysis", ("weighted_objective_coverage", "obj-surface")),
    ("catalog.FailureMode", ("base_probability",)),
    ("simulation.TelemetrySample", ("value",)),
    ("simulation.MissionEvent", ("trigger", "threshold")),
    ("simulation.DecisionChoice", ("effects", "science_days")),
    ("optimization.ArchitectureNode", ("attributes", "mass_kg")),
    ("optimization.ArchitectureCandidate", ("objective_vector", "lifecycle_cost")),
    ("uncertainty.RobustnessResult", ("probability_feasible",)),
    ("uncertainty.DistributionSpec", ("mode",)),
    ("science_belief.BeliefState", ("entropy_bits",)),
    ("operations.ContactWindow", ("max_downlink_bits",)),
    ("operations.BufferPoint", ("bits",)),
    ("operations.MissionSchedule", ("data_lost_bits",)),
    ("simulation.PhaseTransition", ("mission_day",)),
    ("optimization.MetricChange", ("after",)),
    ("analyst.Recommendation", ("metric_after", "data_margin_fraction")),
    ("health.DetectorConfig", ("lam",)),
    ("health.Anomaly", ("observed",)),
]


def _set_path(data: dict[str, Any], path: tuple[str, ...], value: object) -> None:
    for key in path[:-1]:
        data = data[key]
    assert path[-1] in data, path
    data[path[-1]] = value


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
@pytest.mark.parametrize(("name", "path"), NAN_CASES)
def test_non_finite_floats_rejected(
    name: str,
    path: tuple[str, ...],
    bad: float,
    builders: dict[str, Callable[[], BaseModel]],
) -> None:
    instance = builders[name]()
    data = instance.model_dump()
    _set_path(data, path, bad)
    with pytest.raises(ValidationError):
        type(instance).model_validate(data)


def test_nan_literal_rejected_in_json(builders: dict[str, Callable[[], BaseModel]]) -> None:
    from app.schemas.analysis import MissionAnalysis

    text = builders["analysis.MissionAnalysis"]().model_dump_json(by_alias=True)
    text = text.replace('"riskIndex":0.3', '"riskIndex":NaN', 1)
    assert "NaN" in text
    with pytest.raises(ValidationError):
        MissionAnalysis.model_validate_json(text)


# --- semantic invariants -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("feasibility", "status", "ready", "ok"),
    [
        ("feasible", "fail", False, False),  # failed hard constraint => must be infeasible
        ("marginal", "fail", False, False),
        ("infeasible", "warning", False, False),  # infeasible needs a failed constraint
        ("infeasible", "fail", True, False),  # never mission-ready when infeasible
        ("infeasible", "fail", False, True),
        ("feasible", "pass", True, True),
        ("marginal", "warning", True, True),
    ],
)
def test_feasibility_consistent_with_constraints(
    feasibility: str,
    status: str,
    ready: bool,
    ok: bool,
    builders: dict[str, Callable[[], BaseModel]],
) -> None:
    instance = builders["analysis.MissionAnalysis"]()
    data = instance.model_dump()
    data["mission_ready"] = ready
    data["feasibility"] = feasibility
    data["constraints"][0]["status"] = status
    if ok:
        type(instance).model_validate(data)
    else:
        with pytest.raises(ValidationError):
            type(instance).model_validate(data)


def test_score_breakdown_requires_five_unique_dimensions(
    builders: dict[str, Callable[[], BaseModel]],
) -> None:
    instance = builders["analysis.ScoreBreakdown"]()
    data = instance.model_dump()
    data["dimensions"] = data["dimensions"][:4]
    with pytest.raises(ValidationError):
        type(instance).model_validate(data)
    data = instance.model_dump()
    data["dimensions"][1]["id"] = "scientific-return"
    with pytest.raises(ValidationError):
        type(instance).model_validate(data)


@pytest.mark.parametrize(
    "spec",
    [
        {"kind": "normal", "mean": 1.0},
        {"kind": "normal", "mean": 1.0, "std_dev": 0.0},
        {"kind": "uniform", "min": 2.0, "max": 1.0},
        {"kind": "triangular", "min": 0.0, "mode": 2.0, "max": 1.0},
    ],
)
def test_invalid_distribution_rejected(spec: dict[str, Any]) -> None:
    from app.schemas.uncertainty import DistributionSpec

    with pytest.raises(ValidationError):
        DistributionSpec.model_validate(spec)


def test_wilson_interval_must_be_ordered_fraction(
    builders: dict[str, Callable[[], BaseModel]],
) -> None:
    data = builders["uncertainty.RobustnessResult"]().model_dump()
    data["feasibility_wilson_95"] = (0.9, 0.1)
    with pytest.raises(ValidationError):
        type(builders["uncertainty.RobustnessResult"]()).model_validate(data)


def test_belief_probabilities_must_sum_to_one(builders: dict[str, Callable[[], BaseModel]]) -> None:
    data = builders["science_belief.BeliefState"]().model_dump()
    data["hypotheses"][0]["probability"] = 0.9
    with pytest.raises(ValidationError):
        type(builders["science_belief.BeliefState"]()).model_validate(data)


def test_time_windows_must_be_ordered(builders: dict[str, Callable[[], BaseModel]]) -> None:
    for key in ("operations.ObservationOpportunity", "operations.ContactWindow"):
        instance = builders[key]()
        data = instance.model_dump()
        data["end"] = data["start"] - 1.0
        with pytest.raises(ValidationError):
            type(instance).model_validate(data)


def test_strict_bools(builders: dict[str, Callable[[], BaseModel]]) -> None:
    from app.schemas.mission import ComponentSelection, MeasurementRequirement

    data = builders["mission.MeasurementRequirement"]().model_dump()
    data["required"] = "true"
    with pytest.raises(ValidationError):
        MeasurementRequirement.model_validate(data)
    with pytest.raises(ValidationError):
        ComponentSelection.model_validate({"component_id": "c", "quantity": 1, "enabled": 1})


def test_package_schema_version_is_checked(builders: dict[str, Callable[[], BaseModel]]) -> None:
    data = builders["evidence.MissionPackage"]().model_dump()
    data["package_schema_version"] = "9.9"
    with pytest.raises(ValidationError):
        type(builders["evidence.MissionPackage"]()).model_validate(data)


# --- layering ----------------------------------------------------------------------------

FORBIDDEN_IMPORT_PREFIXES = (
    "app.domain",
    "app.api",
    "app.services",
    "app.integrations",
    "app.infrastructure",
    "app.main",
    "fastapi",
)


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                names.append("." * node.level + (node.module or ""))
            else:
                names.append(node.module or "")
    return names


def test_schema_modules_do_not_import_outer_layers() -> None:
    offenders = {
        p.name: bad
        for p in sorted(SCHEMA_DIR.glob("*.py"))
        if (bad := [n for n in _imports(p) if n.startswith(FORBIDDEN_IMPORT_PREFIXES + (".",))])
    }
    assert not offenders, f"schemas must be a leaf layer: {offenders}"


def test_sanitize_title_lives_in_schemas_and_is_reexported() -> None:
    from app.domain.mission import validation
    from app.schemas import _text

    assert validation.sanitize_title is _text.sanitize_title
    assert _text.sanitize_title("<b>Hi</b>\x00  there") == "Hi there"
    assert len(_text.sanitize_title("x" * 200)) == _text.MAX_TITLE_LENGTH


def test_snapshot_rewrite_refused_in_ci(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UPDATE_SNAPSHOTS", "1")
    monkeypatch.setenv("CI", "true")
    with pytest.raises(pytest.fail.Exception, match="not allowed in CI"):
        test_schema_snapshot("api")


# --- fix round 1 / ruling R10 invariants --------------------------------------------------


def _invalid(instance: BaseModel, mutate: Callable[[dict[str, Any]], None]) -> None:
    data = instance.model_dump()
    mutate(data)
    with pytest.raises(ValidationError):
        type(instance).model_validate(data)


def test_run_snapshot_and_manifest_must_match(
    builders: dict[str, Callable[[], BaseModel]],
) -> None:
    run = builders["simulation.MissionRun"]()

    def other_revision(d: dict[str, Any]) -> None:
        d["input_snapshot"]["design_revision"] = 2

    def other_mission(d: dict[str, Any]) -> None:
        d["input_snapshot"]["mission_id"] = "other"

    def other_seed(d: dict[str, Any]) -> None:
        d["manifest"]["seed"] = 1

    def other_engine(d: dict[str, Any]) -> None:
        d["manifest"]["engine_version"] = "9.9.9"

    def unordered_transitions(d: dict[str, Any]) -> None:
        d["phase_transitions"] = (
            {"phase": "science-ops", "mission_day": 250.0},
            {"phase": "cruise", "mission_day": 10.0},
        )

    for mutate in (other_revision, other_mission, other_seed, other_engine, unordered_transitions):
        _invalid(run, mutate)


def test_autonomy_log_defaults_empty_and_records_belief(
    builders: dict[str, Callable[[], BaseModel]],
) -> None:
    from app.schemas.simulation import MissionRun

    run = builders["simulation.MissionRun"]()
    assert isinstance(run, MissionRun)
    assert run.autonomy_log[0].belief.hypotheses[0].hypothesis_id == "hyp-volatile"
    data = run.model_dump()
    del data["autonomy_log"]
    assert MissionRun.model_validate(data).autonomy_log == ()


def test_package_runs_keep_their_own_snapshot(
    builders: dict[str, Callable[[], BaseModel]],
) -> None:
    from app.schemas.evidence import MissionPackage

    pkg = builders["evidence.MissionPackage"]()
    assert isinstance(pkg, MissionPackage)
    newer = pkg.mission.model_copy(update={"design_revision": 4})
    data = pkg.model_dump()
    data["mission"] = newer.model_dump()
    again = MissionPackage.model_validate(data)
    assert again.runs[0].input_snapshot.design_revision == 3

    def foreign_run(d: dict[str, Any]) -> None:
        d["mission"]["mission_id"] = "someone-else"

    _invalid(pkg, foreign_run)


def test_evidence_reexports_run_manifest() -> None:
    from app.schemas import evidence, simulation

    assert evidence.MissionRunManifest is simulation.MissionRunManifest


def test_optimization_ids_must_reference_candidates(
    builders: dict[str, Callable[[], BaseModel]],
) -> None:
    result = builders["optimization.OptimizationResult"]()

    def unknown_front(d: dict[str, Any]) -> None:
        d["pareto_front_ids"] = ["nope"]

    def unknown_archetype(d: dict[str, Any]) -> None:
        d["archetypes"]["lean"] = "nope"

    def unknown_near_miss(d: dict[str, Any]) -> None:
        d["near_misses"] = ["nope"]

    def front_and_near_miss(d: dict[str, Any]) -> None:
        d["near_misses"] = ["cand-000"]

    for mutate in (unknown_front, unknown_archetype, unknown_near_miss, front_and_near_miss):
        _invalid(result, mutate)


def test_schedule_consistency(builders: dict[str, Callable[[], BaseModel]]) -> None:
    schedule = builders["operations.MissionSchedule"]()

    def overlap(d: dict[str, Any]) -> None:
        d["accepted"] = ["opp-1", "opp-2"]

    def silent_loss(d: dict[str, Any]) -> None:
        d["data_lost_bits"] = 1.0

    for mutate in (overlap, silent_loss):
        _invalid(schedule, mutate)
    data = schedule.model_dump()
    data.update(data_lost_bits=1.0, data_loss_risk_accepted=True)
    type(schedule).model_validate(data)
    data["rejected"][0]["reason_code"] = "THERMAL"
    type(schedule).model_validate(data)


def test_graph_edges_reference_nodes(builders: dict[str, Callable[[], BaseModel]]) -> None:
    def dangling(d: dict[str, Any]) -> None:
        d["edges"][0]["to_id"] = "missing"

    def duplicate(d: dict[str, Any]) -> None:
        d["nodes"].append(d["nodes"][0])

    for mutate in (dangling, duplicate):
        _invalid(builders["optimization.ArchitectureGraph"](), mutate)


def test_health_contract_invariants(builders: dict[str, Callable[[], BaseModel]]) -> None:
    def warn_above_crit(d: dict[str, Any]) -> None:
        d["warn"] = 0.5

    def zero_lambda(d: dict[str, Any]) -> None:
        d["lam"] = 0.0

    for mutate in (warn_above_crit, zero_lambda):
        _invalid(builders["health.DetectorConfig"](), mutate)

    def reversed_window(d: dict[str, Any]) -> None:
        d["window_end"] = 1.0

    _invalid(builders["health.Anomaly"](), reversed_window)


def test_simulation_input_experimental_defaults_false(
    builders: dict[str, Callable[[], BaseModel]],
) -> None:
    from app.schemas.simulation import SimulationInput

    data = builders["simulation.SimulationInput"]().model_dump()
    del data["experimental"]
    assert SimulationInput.model_validate(data).experimental is False


def test_fraction_unit_available() -> None:
    from typing import get_args

    from app.schemas.units import Unit

    assert "fraction" in get_args(Unit)
