"""analyze_mission orchestrator (Task 2.8): golden NEO analysis, AC-03 swaps, error policy."""

import json
import math
import os
import random
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from app.config import DEFAULT_CATALOG_DIR, DEFAULT_MISSIONS_DIR, Settings
from app.domain.analysis.orchestrator import (
    ENGINE_VERSION,
    SCENARIO_DEFAULTS,
    ScenarioInputs,
    analyze_mission,
    scenario_inputs_from_template,
)
from app.domain.catalog.loader import Catalog, load_catalog
from app.domain.errors import DomainValidationError
from app.domain.mission.defaults import default_mission_state, list_templates
from app.schemas.analysis import ConstraintResult, MissionAnalysis
from app.schemas.mission import MissionState
from app.schemas.templates import ScenarioTemplate

NOW = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)
LATER = datetime(2027, 1, 1, 0, 0, tzinfo=UTC)
GOLDEN = Path(__file__).resolve().parents[2] / "golden" / "neo_default_analysis.json"
REGEN_HINT = "UPDATE_GOLDEN=1 uv run python -m pytest tests/unit/analysis/test_orchestrator.py"
SCENARIOS = ("neo-rendezvous", "lunar-polar-scout", "earth-observation")


@pytest.fixture(scope="module")
def catalog() -> Catalog:
    return load_catalog(DEFAULT_CATALOG_DIR)


@pytest.fixture(scope="module")
def templates() -> dict[str, ScenarioTemplate]:
    return {t.scenario_id: t for t in list_templates(DEFAULT_MISSIONS_DIR)}


def _state(scenario: str = "neo-rendezvous") -> MissionState:
    return default_mission_state(
        scenario, mission_id="m-golden", seed=42, now=NOW, templates_dir=DEFAULT_MISSIONS_DIR
    )


def _edit(state: MissionState, **arch: Any) -> MissionState:
    dump = state.model_dump()
    dump["architecture"] = {**dump["architecture"], **arch}
    return MissionState.model_validate(dump)


def _run(
    state: MissionState,
    catalog: Catalog,
    templates: dict[str, ScenarioTemplate],
    now: datetime = NOW,
) -> MissionAnalysis:
    return analyze_mission(
        state,
        catalog,
        scenario=scenario_inputs_from_template(templates[state.scenario_id]),
        engine_version=ENGINE_VERSION,
        now=now,
    )


def _c(analysis: MissionAnalysis, cid: str) -> ConstraintResult:
    return next(c for c in analysis.constraints if c.id == cid)


def _issues(analysis: MissionAnalysis) -> dict[str, str]:
    return {c.id: c.status for c in analysis.constraints if c.status in ("fail", "warning")}


def _golden_payload(analysis: MissionAnalysis) -> dict[str, Any]:
    payload = analysis.model_dump(mode="json", by_alias=True)
    del payload["calculatedAt"]
    return payload


def _approx_equal(a: Any, b: Any, path: str = "$") -> None:
    """Exact structure; floats equal within 1e-9 relative (libm may differ by an ulp)."""
    if isinstance(a, float) or isinstance(b, float):
        assert isinstance(a, int | float) and isinstance(b, int | float), path
        assert math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12), f"{path}: {a} != {b}"
    elif isinstance(a, dict):
        assert isinstance(b, dict) and list(a) == list(b), f"{path}: keys differ"
        for k in a:
            _approx_equal(a[k], b[k], f"{path}.{k}")
    elif isinstance(a, list):
        assert isinstance(b, list) and len(a) == len(b), f"{path}: length differs"
        for i, (x, y) in enumerate(zip(a, b, strict=True)):
            _approx_equal(x, y, f"{path}[{i}]")
    else:
        assert a == b, f"{path}: {a!r} != {b!r}"


# --- (a) golden -----------------------------------------------------------------------


def test_neo_default_matches_golden(
    catalog: Catalog, templates: dict[str, ScenarioTemplate]
) -> None:
    payload = _golden_payload(_run(_state(), catalog, templates))
    if os.environ.get("UPDATE_GOLDEN") == "1":
        if os.environ.get("CI"):
            pytest.fail("UPDATE_GOLDEN is not allowed in CI; golden files must be committed")
        GOLDEN.parent.mkdir(exist_ok=True)
        text = json.dumps(payload, indent=2, sort_keys=False) + "\n"
        GOLDEN.write_text(text, encoding="utf-8", newline="\n")
    assert GOLDEN.exists(), f"missing golden {GOLDEN.name}; run: {REGEN_HINT}"
    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
    _approx_equal(payload, expected)
    assert payload["engineVersion"] == "0.1.0"


def test_golden_regen_refused_in_ci(
    monkeypatch: pytest.MonkeyPatch, catalog: Catalog, templates: dict[str, ScenarioTemplate]
) -> None:
    monkeypatch.setenv("UPDATE_GOLDEN", "1")
    monkeypatch.setenv("CI", "true")
    with pytest.raises(pytest.fail.Exception, match="not allowed in CI"):
        test_neo_default_matches_golden(catalog, templates)


def test_engine_version_matches_settings_default() -> None:
    assert ENGINE_VERSION == "0.1.0"
    assert Settings.model_fields["engine_version"].default == ENGINE_VERSION


# --- NEO demo story -----------------------------------------------------------------


def test_neo_starter_lowgain_story(
    catalog: Catalog, templates: dict[str, ScenarioTemplate]
) -> None:
    a = _run(_state(), catalog, templates)
    issues = _issues(a)
    assert issues["link-margin"] == "fail"
    assert issues["data-return"] == "warning"
    assert a.feasibility == "infeasible" and a.mission_ready is False
    link = _c(a, "link-margin")
    assert link.actual is not None and link.actual.value < 0.0
    assert a.budgets.data_downlinked_bits.value == 0.0
    assert a.budgets.data_generated_bits.value == pytest.approx(12.96e9)
    assert a.budgets.data_margin_fraction == pytest.approx(-1.0)
    assert a.science.collected_fraction > 0.0 and a.science.returned_fraction == 0.0
    assert "link-margin" in a.top_drivers
    # hard gates that the template tuning promises are healthy
    for cid in ("mass-launch-limit", "delta-v-margin", "peak-power", "energy-closure",
                "battery-reserve", "data-buffer", "budget", "trajectory-valid"):  # fmt: skip
        assert _c(a, cid).status == "pass", cid


def test_neo_medium_radio_clears_link_and_data_return(
    catalog: Catalog, templates: dict[str, ScenarioTemplate]
) -> None:
    low = _run(_state(), catalog, templates)
    med = _run(_edit(_state(), communications_id="comms-xband-medium"), catalog, templates)
    issues = _issues(med)
    assert "link-margin" not in issues and "data-return" not in issues
    assert _c(med, "link-margin").status == "pass"
    assert _c(med, "data-return").status == "pass"
    link = _c(med, "link-margin")
    assert link.actual is not None and link.actual.value == pytest.approx(6.709, abs=1e-3)
    assert med.budgets.data_downlinked_bits.value == pytest.approx(12.96e9)
    assert med.budgets.data_margin_fraction == pytest.approx(17.1072e9 / 12.96e9 - 1.0)
    # (c) swap changes link margin and data margin
    assert _c(low, "link-margin").actual != link.actual
    assert low.budgets.data_margin_fraction != med.budgets.data_margin_fraction
    assert med.feasibility != "infeasible"
    assert med.science.returned_fraction > low.science.returned_fraction


# --- (b) AC-03: adding an instrument propagates -----------------------------------


def test_adding_spectrometer_changes_every_budget(
    catalog: Catalog, templates: dict[str, ScenarioTemplate]
) -> None:
    spectro = "inst-vnir-spectrometer"
    p = catalog[spectro].parameters
    assert p["mass"].value > 0 and p["power_w"].value > 0 and p["data_rate"].value > 0
    # medium radio so returned science (and hence coverage_score) is non-zero
    radio = "comms-xband-medium"
    without = _edit(_state(), instrument_ids=("inst-hires-camera",), communications_id=radio)
    with_ = _edit(_state(), instrument_ids=("inst-hires-camera", spectro), communications_id=radio)
    a, b = _run(without, catalog, templates), _run(with_, catalog, templates)
    assert b.budgets.dry_mass_kg.value == pytest.approx(a.budgets.dry_mass_kg.value + 3.0)
    assert b.budgets.average_power_w.value > a.budgets.average_power_w.value
    assert b.budgets.data_generated_bits.value > a.budgets.data_generated_bits.value
    assert b.budgets.estimated_cost_usd.value > a.budgets.estimated_cost_usd.value
    assert b.science.coverage_score != a.science.coverage_score
    assert _c(a, "science-mandatory-coverage").status == "fail"  # no VNIR capability
    assert "meas-vnir-spectra" in a.science.missing_requirements


# --- (d) determinism ---------------------------------------------------------------


def test_repeated_calls_identical_except_calculated_at(
    catalog: Catalog, templates: dict[str, ScenarioTemplate]
) -> None:
    a = _run(_state(), catalog, templates)
    b = _run(_state(), catalog, templates)
    c = _run(_state(), catalog, templates, now=LATER)
    assert a.model_dump_json() == b.model_dump_json()
    assert c.calculated_at == LATER
    assert _golden_payload(a) == _golden_payload(c)


# --- context wiring ----------------------------------------------------------------


def test_context_flags_come_from_real_inputs(
    catalog: Catalog, templates: dict[str, ScenarioTemplate]
) -> None:
    from app.domain.analysis.orchestrator import build_context

    scen = scenario_inputs_from_template(templates["neo-rendezvous"])
    ctx = build_context(_state(), catalog, scenario=scen)
    assert ctx.required_measurement_ids == ("meas-shape-model", "meas-vnir-spectra")
    assert ctx.pointing_ok is True and ctx.power_ok is True
    # coarse ADCS (0.5 deg) cannot meet the hi-res camera's 0.05 deg need
    coarse = build_context(_edit(_state(), adcs_id="adcs-basic"), catalog, scenario=scen)
    assert coarse.pointing_ok is False
    # a tiny array at 1.3 AU cannot power the starter design
    weak = build_context(_edit(_state(), power_id="power-small"), catalog, scenario=scen)
    assert weak.power_ok is False
    assert len(ctx.contact_links) == len(_state().operations.downlink_plan)


def test_power_shortfall_zeroes_science(
    catalog: Catalog, templates: dict[str, ScenarioTemplate]
) -> None:
    a = _run(
        _edit(_state(), power_id="power-small", communications_id="comms-xband-medium"),
        catalog,
        templates,
    )
    assert a.feasibility == "infeasible"
    assert a.science.collected_fraction == 0.0
    assert {"energy-closure", "battery-reserve"} & set(_issues(a))


def test_budgets_carry_units_and_provenance(
    catalog: Catalog, templates: dict[str, ScenarioTemplate]
) -> None:
    b = _run(_state(), catalog, templates).budgets
    units = {
        "dry_mass_kg": "kg", "propellant_mass_kg": "kg", "wet_mass_kg": "kg",
        "average_power_w": "W", "peak_power_w": "W", "data_generated_bits": "bit",
        "data_downlinked_bits": "bit", "required_delta_v_km_per_s": "km/s",
        "available_delta_v_km_per_s": "km/s", "estimated_cost_usd": "USD",
    }  # fmt: skip
    for name, unit in units.items():
        q = getattr(b, name)
        assert q.unit == unit, name
        assert q.provenance.source_version, name
        expected = "gameplay-estimate" if name == "estimated_cost_usd" else "derived"
        assert q.provenance.fidelity == expected, name
    assert b.wet_mass_kg.value == pytest.approx(b.dry_mass_kg.value + b.propellant_mass_kg.value)
    assert b.required_delta_v_km_per_s.value == pytest.approx(0.25)
    assert b.estimated_cost_usd.uncertainty is not None
    assert b.estimated_cost_usd.uncertainty.distribution == "interval"


def test_assumptions_are_merged_and_deduplicated(
    catalog: Catalog, templates: dict[str, ScenarioTemplate]
) -> None:
    from app.domain.analysis import (
        comms,
        constraints,
        cost,
        data,
        mass,
        orchestrator,
        power,
        propulsion,
        reliability,
        science,
        score,
        thermal,
    )

    a = _run(_state(), catalog, templates)
    assert len(a.assumptions) == len(set(a.assumptions))
    groups = {
        "orchestrator": orchestrator.ORCHESTRATOR_ASSUMPTIONS,
        "scenario": scenario_inputs_from_template(templates["neo-rendezvous"]).assumptions,
        "mass": mass.ASSUMPTIONS, "propulsion": propulsion.ASSUMPTIONS,
        "power": power.ASSUMPTIONS, "comms": comms.ASSUMPTIONS, "data": data.ASSUMPTIONS,
        "science": science.science_assumptions(), "cost": cost.ASSUMPTIONS,
        "reliability": reliability.RELIABILITY_ASSUMPTIONS,
        "thermal": thermal.THERMAL_ASSUMPTIONS,
        "constraints": constraints.CONSTRAINT_ASSUMPTIONS, "score": score.SCORE_ASSUMPTIONS,
    }  # fmt: skip
    for name, group in groups.items():
        assert group, name
        missing = [s for s in group if s not in a.assumptions]
        assert not missing, (name, missing)
    assert any("1.3 AU" in s for s in a.assumptions)
    assert any("0.95" in s and "discharge" in s.lower() for s in a.assumptions)


def test_eclipse_peak_is_checked_against_battery_only_supply(
    catalog: Catalog, templates: dict[str, ScenarioTemplate]
) -> None:
    from app.domain.analysis.orchestrator import build_context

    base = scenario_inputs_from_template(templates["neo-rendezvous"])
    dark = ScenarioInputs(
        reference_earth_range_m=base.reference_earth_range_m,
        sun_distance_au=base.sun_distance_au,
        thermal_exposure=base.thermal_exposure,
        eclipse_fraction=0.1,
    )
    # power-medium: 90 Wh battery -> 90 W in eclipse; sunlit supply ~170 W; science peak 100 W
    state = _edit(_state(), power_id="power-medium")
    ctx = build_context(state, catalog, scenario=dark)
    assert ctx.supply_power_w == pytest.approx(90.0)
    assert ctx.peak_power_w == pytest.approx(100.0)
    assert ctx.power_ok is False
    a = analyze_mission(state, catalog, scenario=dark, engine_version=ENGINE_VERSION, now=NOW)
    assert _c(a, "peak-power").status == "fail"
    # without eclipse the same design is checked against the sunlit supply and passes
    lit = build_context(state, catalog, scenario=base)
    assert lit.supply_power_w > 160.0
    assert _c(_run(state, catalog, templates), "peak-power").status == "pass"


def test_pointing_uses_the_assigned_instrument(
    catalog: Catalog, templates: dict[str, ScenarioTemplate]
) -> None:
    from app.domain.analysis.orchestrator import build_context

    scen = scenario_inputs_from_template(templates["neo-rendezvous"])
    radio = "comms-xband-medium"
    # hires (20 Mbit/s, needs 0.05 deg) is assigned to the shape model over the wide camera
    # (1.5 Mbit/s, needs 0.5 deg); adcs-basic gives 0.5 deg, so shape-model pointing fails
    # even though the wide camera alone would be pointed well enough.
    both = _edit(
        _state(), adcs_id="adcs-basic", communications_id=radio,
        instrument_ids=("inst-hires-camera", "inst-wide-camera"),
    )  # fmt: skip
    wide = _edit(
        _state(), adcs_id="adcs-basic", communications_id=radio,
        instrument_ids=("inst-wide-camera",),
    )  # fmt: skip
    assert build_context(both, catalog, scenario=scen).pointing_ok is False
    a, b = _run(both, catalog, templates), _run(wide, catalog, templates)
    assert a.science.weighted_objective_coverage["obj-morphology"] == 0.0
    assert b.science.weighted_objective_coverage["obj-morphology"] > 0.0
    # only REQUIRED measurements count: the wide camera alone meets the shape-model need
    # (VNIR has no capable instrument, so it is not a pointing question)
    assert build_context(wide, catalog, scenario=scen).pointing_ok is True


def test_contract_validation_error_is_a_failed_analysis(
    monkeypatch: pytest.MonkeyPatch, catalog: Catalog, templates: dict[str, ScenarioTemplate]
) -> None:
    from app.domain.analysis import orchestrator
    from app.schemas.analysis import ReliabilityAnalysis

    def bad_reliability(_: object) -> ReliabilityAnalysis:
        return ReliabilityAnalysis(
            nominal_reliability=2.0, risk_index=0.0, single_point_failures=[]
        )

    monkeypatch.setattr(orchestrator, "reliability", bad_reliability)
    a = _run(_state(), catalog, templates)
    c = _c(a, "model-input-invalid")
    assert c.status == "fail" and "MODEL_INPUT_INVALID" in c.explanation
    assert "nominal_reliability" in c.explanation
    assert a.feasibility == "infeasible" and a.mission_ready is False


def test_jpl_trajectory_delta_v_is_informational(
    catalog: Catalog, templates: dict[str, ScenarioTemplate]
) -> None:
    dump = _state().model_dump()
    dump["trajectory"] = {**dump["trajectory"], "provider": "jpl-mdesign"}
    a = _run(MissionState.model_validate(dump), catalog, templates)
    assert a.budgets.required_delta_v_km_per_s.value == 0.0


def test_all_scenarios_analyse(catalog: Catalog, templates: dict[str, ScenarioTemplate]) -> None:
    for sid in SCENARIOS:
        a = _run(_state(sid), catalog, templates)
        assert a.mission_id == "m-golden" and a.design_revision == 0
        assert a.catalog_version == catalog.version
        assert len(a.score.dimensions) == 5


def test_scenario_inputs_defaults_and_validation(templates: dict[str, ScenarioTemplate]) -> None:
    neo = scenario_inputs_from_template(templates["neo-rendezvous"])
    assert neo.reference_earth_range_m == templates["neo-rendezvous"].reference_earth_range_m
    assert neo.sun_distance_au == SCENARIO_DEFAULTS["neo-rendezvous"].sun_distance_au
    assert neo.thermal_exposure == "cold" and neo.eclipse_fraction == 0.0
    for bad in (
        {"reference_earth_range_m": 0.0},
        {"sun_distance_au": -1.0},
        {"eclipse_fraction": 1.0},
        {"power_cycle_s": 0.0},
        {"reference_earth_range_m": math.nan},
    ):
        with pytest.raises(DomainValidationError):
            ScenarioInputs(**{"reference_earth_range_m": 1e9, **bad})  # type: ignore[arg-type]


def test_eclipse_drains_battery(catalog: Catalog, templates: dict[str, ScenarioTemplate]) -> None:
    base = scenario_inputs_from_template(templates["neo-rendezvous"])
    dark = ScenarioInputs(
        reference_earth_range_m=base.reference_earth_range_m,
        sun_distance_au=base.sun_distance_au,
        thermal_exposure=base.thermal_exposure,
        eclipse_fraction=0.5,
    )
    a = analyze_mission(_state(), catalog, scenario=dark, engine_version="0.1.0", now=NOW)
    b = _run(_state(), catalog, templates)
    assert _c(a, "battery-reserve").status == "fail"
    assert _c(b, "battery-reserve").status == "pass"


# --- (e) error policy -----------------------------------------------------------------


def test_missing_catalogue_item_is_a_failed_analysis_not_an_exception(
    catalog: Catalog, templates: dict[str, ScenarioTemplate]
) -> None:
    a = _run(_edit(_state(), communications_id="comms-does-not-exist"), catalog, templates)
    c = _c(a, "catalog-item-not-found")
    assert c.status == "fail" and c.severity == 3
    assert "CATALOG_ITEM_NOT_FOUND" in c.explanation and "comms-does-not-exist" in c.explanation
    assert a.feasibility == "infeasible" and a.mission_ready is False
    assert a.budgets.dry_mass_kg.provenance.fidelity == "not-modelled"
    assert a.top_drivers == ["catalog-item-not-found"]
    assert len(a.constraints) == 1


def test_discipline_error_is_a_failed_analysis(
    catalog: Catalog, templates: dict[str, ScenarioTemplate]
) -> None:
    broken = catalog["comms-xband-lowgain"].model_dump()
    del broken["parameters"]["tx_power"]
    comps = tuple(
        type(catalog[k]).model_validate(broken) if k == "comms-xband-lowgain" else catalog[k]
        for k in catalog
    )
    a = _run(_state(), Catalog(catalog.version, comps), templates)
    c = _c(a, "model-input-invalid")
    assert c.status == "fail" and "MISSING_PARAMETER" in c.explanation
    assert a.feasibility == "infeasible"


# --- (g) no NaN / inf anywhere (seeded random designs; R4: no hypothesis library) ---------


def _walk_finite(node: Any, path: str = "$") -> None:
    if isinstance(node, float):
        assert math.isfinite(node), path
    elif isinstance(node, dict):
        for k, v in node.items():
            _walk_finite(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            _walk_finite(v, f"{path}[{i}]")
    elif isinstance(node, str):
        assert node.lower() not in ("nan", "inf", "-inf", "infinity"), path


_SLOTS = {
    "launch_vehicle_id": "launch", "bus_id": "bus", "propulsion_id": "propulsion",
    "power_id": "power", "adcs_id": "adcs", "communications_id": "communications",
    "thermal_id": "thermal", "cdh_id": "cdh", "ground_segment_id": "ground",
}  # fmt: skip


def _random_state(rng: random.Random, catalog: Catalog) -> MissionState:
    dump = _state(rng.choice(SCENARIOS)).model_dump()
    for slot, cat in _SLOTS.items():
        if rng.random() < 0.5:
            dump["architecture"][slot] = rng.choice(catalog.by_category(cat)).id
    insts = [c.id for c in catalog.by_category("instrument")]
    dump["architecture"]["instrument_ids"] = tuple(rng.sample(insts, rng.randint(0, 3)))
    ops = dump["operations"]
    ops["observation_plan"] = tuple(
        {**o, "duty_cycle": rng.choice([0.0, rng.random(), 1.0])} for o in ops["observation_plan"]
    )
    if rng.random() < 0.2:
        ops["downlink_plan"] = ()
    if rng.random() < 0.2:
        ops["observation_plan"] = ()
    if rng.random() < 0.2:
        dump["constraints"]["launch_mass_limit_kg"] = None
    return MissionState.model_validate(dump)


def test_random_designs_never_serialise_nan_or_inf(
    catalog: Catalog, templates: dict[str, ScenarioTemplate]
) -> None:
    rng = random.Random(20261113)
    for _ in range(60):
        state = _random_state(rng, catalog)
        a = _run(state, catalog, templates)
        _walk_finite(a.model_dump(mode="json", by_alias=True))
        assert not (a.mission_ready and a.feasibility == "infeasible")


@pytest.mark.parametrize(
    ("change", "valid"),
    [
        ({"option_id": "  "}, False),
        ({"arrival_date": "2031-01-01"}, False),  # before the 2031-03-01 departure
        ({"time_of_flight_days": -1.0}, False),
        ({"mission_delta_v_km_per_s": None}, True),
    ],
)
def test_trajectory_validity_and_missing_delta_v(
    change: dict[str, Any], valid: bool, catalog: Catalog, templates: dict[str, ScenarioTemplate]
) -> None:
    dump = _state().model_dump()
    dump["trajectory"] = {**dump["trajectory"], **change}
    a = _run(MissionState.model_validate(dump), catalog, templates)
    assert (_c(a, "trajectory-valid").status == "pass") is valid
    if valid:
        assert a.budgets.required_delta_v_km_per_s.value == 0.0
