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


def test_mission_ready_requires_no_failed_constraint(
    builders: dict[str, Callable[[], BaseModel]],
) -> None:
    data = builders["analysis.MissionAnalysis"]().model_dump()
    data["mission_ready"] = True
    data["feasibility"] = "feasible"
    data["constraints"][0]["status"] = "fail"
    with pytest.raises(ValidationError, match="mission_ready"):
        type(builders["analysis.MissionAnalysis"]()).model_validate(data)


def test_mission_ready_requires_feasible(builders: dict[str, Callable[[], BaseModel]]) -> None:
    data = builders["analysis.MissionAnalysis"]().model_dump()
    data["mission_ready"] = True
    data["feasibility"] = "infeasible"
    data["constraints"] = []
    with pytest.raises(ValidationError, match="mission_ready"):
        type(builders["analysis.MissionAnalysis"]()).model_validate(data)


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
