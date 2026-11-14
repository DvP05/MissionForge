"""STM/MTM projections and traversal helpers (Task 6.1)."""

import pytest

from app.domain.architecture_graph import (
    build_traceability_matrices,
    downstream,
    find_path,
    upstream,
)

from ._support import SCENARIOS, catalog, edit_arch, graph_of, state


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_stm_consistent_with_mission_entities(scenario: str) -> None:
    s = state(scenario)
    stm, _ = build_traceability_matrices(graph_of(s))
    expected = [(o.id, r.id) for o in s.science_objectives for r in o.required_measurements]
    assert sorted((row.objective_id, row.requirement_id) for row in stm) == sorted(expected)
    instruments = {cid: catalog()[cid] for cid in s.architecture.instrument_ids}
    for row in stm:
        capable = {cid for cid, c in instruments.items() if row.capability in c.capabilities}
        assert set(row.instrument_ids) == capable
        assert (row.status == "uncovered") == (not capable)
        scheduled = sum(
            o.measurement_id == row.requirement_id for o in s.operations.observation_plan
        )
        assert row.observation_count == scheduled


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_mtm_consistent_with_stm(scenario: str) -> None:
    s = state(scenario)
    stm, mtm = build_traceability_matrices(graph_of(s))
    assert [r.instrument_id for r in mtm] == list(dict.fromkeys(s.architecture.instrument_ids))
    for row in mtm:
        served = {r.requirement_id for r in stm if row.instrument_id in r.instrument_ids}
        assert set(row.requirement_ids) == served
        assert s.architecture.power_id in row.subsystem_ids
        assert s.architecture.cdh_id in row.subsystem_ids


def test_stm_shows_uncovered_row_after_removal() -> None:
    s = edit_arch(state(), instrument_ids=("inst-hires-camera",))
    stm, mtm = build_traceability_matrices(graph_of(s))
    row = next(r for r in stm if r.requirement_id == "meas-vnir-spectra")
    assert row.status == "uncovered" and row.instrument_ids == ()
    assert [r.instrument_id for r in mtm] == ["inst-hires-camera"]


def test_upstream_and_downstream() -> None:
    g = graph_of(state())
    down = downstream(g, "instrument:inst-vnir-spectrometer")
    assert "objective:obj-composition" in down and "subsystem:power" in down
    assert "instrument:inst-vnir-spectrometer" not in down
    up = upstream(g, "objective:obj-composition")
    assert "instrument:inst-vnir-spectrometer" in up and "requirement:meas-vnir-spectra" in up
    with pytest.raises(KeyError):
        downstream(g, "nope")


def test_find_path_none_cases() -> None:
    g = graph_of(state())
    assert find_path(g, "objective:obj-composition", "instrument:inst-vnir-spectrometer") is None
    assert find_path(g, "nope", "subsystem:power") is None
    assert find_path(g, "subsystem:power", "subsystem:power") == ["subsystem:power"]
