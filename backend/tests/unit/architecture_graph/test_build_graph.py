"""build_architecture_graph (Task 6.1, architecture 19.1 / 21 "Architecture graph")."""

import pytest

from app.domain.architecture_graph import (
    CONSTRAINT_ATTR_PREFIX,
    build_architecture_graph,
    find_path,
    nodes_for_constraint,
)
from app.schemas.optimization import ArchitectureGraph

from ._support import SCENARIOS, analyse, catalog, edit_arch, graph_of, node, state


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_no_edge_references_a_missing_node(scenario: str) -> None:
    g = graph_of(state(scenario))
    ids = {n.id for n in g.nodes}
    assert len(ids) == len(g.nodes)
    assert all(e.from_id in ids and e.to_id in ids for e in g.edges)
    # The frozen contract re-checks the same invariant.
    ArchitectureGraph.model_validate(g.model_dump())


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_every_edge_has_kind_and_rationale(scenario: str) -> None:
    g = graph_of(state(scenario))
    assert g.edges
    assert all(e.kind and e.rationale.strip() for e in g.edges)
    assert len({e.id for e in g.edges}) == len(g.edges)


def test_stable_ids_and_deterministic_output() -> None:
    s = state()
    first, second = graph_of(s), graph_of(s)
    assert first.model_dump_json() == second.model_dump_json()
    # A new revision of the same design keeps every id.
    bumped = edit_arch(s)
    assert [n.id for n in graph_of(bumped).nodes] == [n.id for n in first.nodes]
    assert [e.id for e in graph_of(bumped).edges] == [e.id for e in first.edges]


def test_does_not_mutate_inputs() -> None:
    s = state()
    a = analyse(s)
    s_before, a_before = s.model_dump_json(), a.model_dump_json()
    build_architecture_graph(s, a, catalog())
    assert s.model_dump_json() == s_before
    assert a.model_dump_json() == a_before


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_every_objective_maps_to_requirements(scenario: str) -> None:
    s = state(scenario)
    g = graph_of(s)
    for obj in s.science_objectives:
        reqs = {
            e.from_id
            for e in g.edges
            if e.to_id == f"objective:{obj.id}" and e.from_id.startswith("requirement:")
        }
        assert reqs == {f"requirement:{r.id}" for r in obj.required_measurements}


def test_requirement_is_satisfied_by_capable_instrument() -> None:
    g = graph_of(state())
    assert find_path(g, "instrument:inst-vnir-spectrometer", "objective:obj-composition") == [
        "instrument:inst-vnir-spectrometer",
        "requirement:meas-vnir-spectra",
        "objective:obj-composition",
    ]
    assert node(g, "requirement:meas-vnir-spectra").attributes["status"] != "uncovered"


def test_removing_only_spectrometer_leaves_requirement_uncovered() -> None:
    s = state()
    without = edit_arch(s, instrument_ids=("inst-hires-camera",))
    before, after = analyse(s), analyse(without)
    g = build_architecture_graph(without, after, catalog())

    req = node(g, "requirement:meas-vnir-spectra")
    assert req.attributes["status"] == "uncovered"
    assert not [e for e in g.edges if e.to_id == req.id and e.from_id.startswith("instrument:")]
    assert node(g, "objective:obj-composition").attributes["status"] == "uncovered"
    assert "instrument:inst-vnir-spectrometer" not in {n.id for n in g.nodes}
    # Expected coverage of the objective falls.
    cov_before = before.science.weighted_objective_coverage["obj-composition"]
    cov_after = after.science.weighted_objective_coverage["obj-composition"]
    assert cov_after < cov_before or cov_before == 0
    assert node(g, "objective:obj-composition").attributes["coverage"] == cov_after


def test_instrument_links_to_mass_power_thermal_pointing_and_storage() -> None:
    g = graph_of(state())
    targets = {(e.kind, e.to_id) for e in g.edges if e.from_id == "instrument:inst-hires-camera"}
    assert ("consumes", "subsystem:power") in targets
    assert ("generates", "subsystem:cdh") in targets
    assert ("depends-on", "subsystem:adcs") in targets
    assert ("depends-on", "subsystem:thermal") in targets
    assert ("allocated-to", "subsystem:bus") in targets


def test_data_rate_traces_to_data_buffer_and_downlink() -> None:
    """Payload data rate -> data metric (C&DH budget) -> data-buffer constraint + downlink."""
    g = graph_of(state())
    owners = nodes_for_constraint(g, "data-buffer")
    assert owners == ["subsystem:cdh"]
    cdh = node(g, "subsystem:cdh")
    assert {"dataGeneratedBits", "dataDownlinkedBits", "dataMarginFraction"} <= set(cdh.attributes)
    for inst in ("instrument:inst-hires-camera", "instrument:inst-vnir-spectrometer"):
        assert find_path(g, inst, "subsystem:cdh") == [inst, "subsystem:cdh"]
        path = find_path(g, inst, "contact:0")
        assert path is not None and "subsystem:communications" in path


def test_every_constraint_verdict_is_placed_on_a_node() -> None:
    s = state()
    a = analyse(s)
    g = build_architecture_graph(s, a, catalog())
    unplaced = {"budget", "success-probability"}  # mission-wide, no owning node
    for c in a.constraints:
        if c.id in unplaced:
            continue
        owners = nodes_for_constraint(g, c.id)
        assert owners, c.id
        assert all(node(g, o).attributes[CONSTRAINT_ATTR_PREFIX + c.id] == c.status for o in owners)


def test_observations_link_to_instrument_requirement_and_contact() -> None:
    s = state()
    g = graph_of(s)
    obs = [n for n in g.nodes if n.kind == "observation-task"]
    assert len(obs) == len(s.operations.observation_plan)
    for o in obs:
        kinds = {(e.kind, e.to_id.split(":")[0]) for e in g.edges if e.from_id == o.id}
        assert ("satisfies", "requirement") in kinds
        assert ("allocated-to", "instrument") in kinds
        assert ("downlinks-through", "contact") in kinds
    contacts = [n for n in g.nodes if n.kind == "contact-window"]
    assert len(contacts) == len(s.operations.downlink_plan)


def test_science_products_trace_observation_contact_and_objective() -> None:
    g = graph_of(state())
    product = node(g, "product:meas-vnir-spectra")
    incoming = {e.from_id.split(":")[0] for e in g.edges if e.to_id == product.id}
    outgoing = {e.to_id.split(":")[0] for e in g.edges if e.from_id == product.id}
    assert incoming == {"observation"}
    assert outgoing == {"contact", "objective"}


def test_zero_instruments_and_zero_contacts_do_not_crash() -> None:
    s = state()
    dump = s.model_dump()
    dump["architecture"]["instrument_ids"] = ()
    dump["operations"]["downlink_plan"] = ()
    from app.schemas.mission import MissionState

    empty = MissionState.model_validate(dump)
    g = graph_of(empty)
    reqs = [n for n in g.nodes if n.kind == "measurement-requirement"]
    assert reqs and all(n.attributes["status"] == "uncovered" for n in reqs)
    assert not [n for n in g.nodes if n.kind in ("instrument", "contact-window")]


def test_duplicate_instrument_ids_collapse_into_one_node() -> None:
    s = edit_arch(state(), instrument_ids=("inst-hires-camera", "inst-hires-camera"))
    g = graph_of(s)
    cams = [n for n in g.nodes if n.kind == "instrument"]
    assert len(cams) == 1 and cams[0].attributes["quantity"] == 2
