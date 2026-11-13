"""Scenario templates (Task 1.5): parse, resolve, validate, default NEO starter."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.config import DEFAULT_CATALOG_DIR, DEFAULT_MISSIONS_DIR
from app.domain.catalog.compat import check_compatibility
from app.domain.catalog.loader import Catalog, load_catalog
from app.domain.catalog.resolver import resolve_architecture
from app.domain.errors import DomainValidationError
from app.domain.mission.defaults import default_mission_state, list_templates
from app.domain.mission.validation import validate_mission_state
from app.schemas.mission import MissionState
from app.schemas.templates import ScenarioTemplate

NOW = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)
SCENARIOS = ("neo-rendezvous", "lunar-polar-scout", "earth-observation")
CAPABILITY_VOCAB = {
    "visible-imaging", "shape-model", "vnir-spectroscopy", "thermal-infrared",
    "magnetometry", "plasma-environment", "high-res-imaging", "multispectral-imaging",
}  # fmt: skip


@pytest.fixture(scope="module")
def catalog() -> Catalog:
    return load_catalog(DEFAULT_CATALOG_DIR)


@pytest.fixture(scope="module")
def templates() -> dict[str, ScenarioTemplate]:
    return {t.scenario_id: t for t in list_templates(DEFAULT_MISSIONS_DIR)}


def _state(scenario: str) -> MissionState:
    return default_mission_state(scenario, mission_id="m-1", seed=42, now=NOW)


def test_three_templates_parse(templates: dict[str, ScenarioTemplate]) -> None:
    assert set(templates) == set(SCENARIOS)
    for sid, t in templates.items():
        assert t.scenario_version == "0.1.0"
        assert len(t.top_constraints) == 3
        assert t.narrative.strip() and t.title.strip()
        assert t.mission_state.scenario_id == sid


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_template_resolves_validates_and_is_compatible(scenario: str, catalog: Catalog) -> None:
    state = _state(scenario)
    assert validate_mission_state(state, catalog) == []
    resolved = resolve_architecture(state.architecture, catalog)
    assert check_compatibility(resolved.all_components()) == []


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_measurement_capabilities_use_catalogue_vocabulary(
    scenario: str, templates: dict[str, ScenarioTemplate], catalog: Catalog
) -> None:
    t = templates[scenario]
    caps = {c for comp in catalog.by_category("instrument") for c in comp.capabilities}
    assert caps == CAPABILITY_VOCAB
    objectives = (*t.mission_state.science_objectives, *t.optional_objectives)
    for obj in objectives:
        assert obj.required_measurements, obj.id
        for m in obj.required_measurements:
            assert m.instrument_capability in CAPABILITY_VOCAB


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_selected_instruments_cover_every_measurement(scenario: str, catalog: Catalog) -> None:
    state = _state(scenario)
    have = {c for i in state.architecture.instrument_ids for c in catalog.get(i).capabilities}
    for obj in state.science_objectives:
        for m in obj.required_measurements:
            if m.required:
                assert m.instrument_capability in have, m.id


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_unique_stable_ids_and_plans_reference_measurements(scenario: str) -> None:
    state = _state(scenario)
    ids = [m.id for o in state.science_objectives for m in o.required_measurements]
    assert len(ids) == len(set(ids))
    assert {p.measurement_id for p in state.operations.observation_plan} <= set(ids)


def test_neo_starter_has_exactly_two_objectives() -> None:
    state = _state("neo-rendezvous")
    assert len(state.science_objectives) == 2
    caps = {
        m.instrument_capability for o in state.science_objectives for m in o.required_measurements
    }
    assert {"shape-model", "vnir-spectroscopy"} <= caps
    assert state.title == "Echoes of Origins"


def test_neo_optional_objectives_are_thermal_and_magnetic(
    templates: dict[str, ScenarioTemplate],
) -> None:
    t = templates["neo-rendezvous"]
    caps = {m.instrument_capability for o in t.optional_objectives for m in o.required_measurements}
    assert caps == {"thermal-infrared", "magnetometry"}
    starter_ids = {o.id for o in t.mission_state.science_objectives}
    assert starter_ids.isdisjoint(o.id for o in t.optional_objectives)


def test_neo_trajectory_is_labelled_preset_and_target_is_synthetic(
    templates: dict[str, ScenarioTemplate],
) -> None:
    t = templates["neo-rendezvous"]
    traj = t.mission_state.trajectory
    assert traj.provider == "scenario-preset"
    assert traj.arrival_date is not None and traj.arrival_date > traj.departure_date
    assert traj.c3_km2_per_s2 is not None
    assert traj.departure_v_infinity_km_per_s is not None
    dest = t.mission_state.destination
    assert "illustrative" in dest.name.lower()
    assert dest.source is not None and dest.source.fidelity == "gameplay-estimate"
    notes = " ".join(t.fidelity_notes).lower()
    assert "gameplay" in notes and "jpl" in notes


def test_lunar_and_eo_fidelity_notes(templates: dict[str, ScenarioTemplate]) -> None:
    for sid in ("lunar-polar-scout", "earth-observation"):
        notes = templates[sid].fidelity_notes
        assert "orbit: two-body circular educational preset" in notes
        assert "curated transfer preset; not high-fidelity" in notes
        assert templates[sid].mission_state.trajectory.provider == "scenario-preset"


def test_template_titles() -> None:
    assert _state("lunar-polar-scout").title == "Shadowline"
    assert _state("earth-observation").title == "Blue Sentinel"


def _keys(node: object) -> list[str]:
    out: list[str] = []
    if isinstance(node, dict):
        for k, v in node.items():
            out.append(k.lower())
            out.extend(_keys(v))
    elif isinstance(node, list):
        for v in node:
            out.extend(_keys(v))
    return out


def test_templates_store_no_derived_totals() -> None:
    forbidden = ("total", "analysis", "result", "feasib")
    files = list(DEFAULT_MISSIONS_DIR.glob("*.json"))
    assert len(files) == 3
    for path in files:
        keys = _keys(json.loads(path.read_text(encoding="utf-8")))
        assert not [k for k in keys if any(f in k for f in forbidden)], path.name


def test_default_mission_state_is_deterministic() -> None:
    a, b = _state("neo-rendezvous"), _state("neo-rendezvous")
    assert a == b
    assert a.model_dump_json() == b.model_dump_json()
    assert a.mission_id == "m-1" and a.random_seed == 42
    assert a.created_at == NOW == a.updated_at
    assert a.design_revision == 0


def test_default_mission_state_varies_with_inputs() -> None:
    other = default_mission_state("neo-rendezvous", mission_id="m-2", seed=7, now=NOW)
    assert other.mission_id == "m-2" and other.random_seed == 7
    assert other.architecture == _state("neo-rendezvous").architecture


def test_unknown_scenario_is_rejected() -> None:
    with pytest.raises(DomainValidationError, match="unknown scenario"):
        default_mission_state("nope", mission_id="m", seed=1, now=NOW)


def test_list_templates_is_path_injected(tmp_path: Path) -> None:
    assert list_templates(tmp_path) == []


def test_template_service_uses_default_paths() -> None:
    from app.services import template_service

    assert {t.scenario_id for t in template_service.list_scenario_templates()} == set(SCENARIOS)
    state = template_service.create_default_mission("earth-observation", seed=3)
    assert state.scenario_id == "earth-observation" and state.random_seed == 3
    assert state.mission_id


# --- NEO starter: deliberate, fixable data-buffer warning (gross arithmetic) -------------


def _generated_bits(state: MissionState, catalog: Catalog) -> float:
    cap_rate: dict[str, float] = {}
    for iid in state.architecture.instrument_ids:
        comp = catalog.get(iid)
        for cap in comp.capabilities:
            cap_rate[cap] = max(cap_rate.get(cap, 0.0), comp.parameters["data_rate"].value)
    cap_of = {
        m.id: m.instrument_capability
        for o in state.science_objectives
        for m in o.required_measurements
    }
    return sum(
        cap_rate[cap_of[p.measurement_id]] * p.duration_hours * 3600.0 * p.duty_cycle
        for p in state.operations.observation_plan
    )


def _downlink_bits(state: MissionState, comms_id: str, catalog: Catalog) -> float:
    link_cap = catalog.get(comms_id).parameters["max_data_rate"].value
    return sum(
        min(d.data_rate_bits_per_second, link_cap) * d.duration_minutes * 60.0
        for d in state.operations.downlink_plan
    )


def test_neo_starter_generates_more_data_than_it_can_downlink(catalog: Catalog) -> None:
    state = _state("neo-rendezvous")
    assert state.architecture.communications_id == "comms-xband-lowgain"
    assert "inst-hires-camera" in state.architecture.instrument_ids
    generated = _generated_bits(state, catalog)
    assert generated > 0
    assert generated > _downlink_bits(state, state.architecture.communications_id, catalog)


def test_neo_medium_comms_swap_clears_the_warning(catalog: Catalog) -> None:
    state = _state("neo-rendezvous")
    generated = _generated_bits(state, catalog)
    margin = 1.0 + state.constraints.data_margin_fraction
    assert _downlink_bits(state, "comms-xband-medium", catalog) >= generated * margin
    # the onboard storage is not the problem: generated data fits with margin
    storage = catalog.get(state.architecture.cdh_id).parameters["storage"].value
    assert generated * margin <= storage


def test_neo_starter_mass_within_launch_limit(catalog: Catalog) -> None:
    state = _state("neo-rendezvous")
    r = resolve_architecture(state.architecture, catalog)

    def m(c: object) -> float:
        return c.parameters["mass"].value  # type: ignore[attr-defined,no-any-return]

    mass = (
        m(r.bus) + m(r.power) + m(r.adcs) + m(r.communications) + m(r.thermal) + m(r.cdh)
        + sum(m(i) for i in r.instruments)
        + r.propulsion.parameters["dry_mass"].value
        + r.propulsion.parameters["propellant_capacity"].value
    )  # fmt: skip
    limit = r.launch.parameters["launch_mass_limit"].value
    assert mass * (1 + state.constraints.mass_margin_fraction) < limit
    assert state.constraints.launch_mass_limit_kg == limit
