"""Trade-study metric deltas (Task 3.5): alternative minus base, undefined values omitted."""

import math
from datetime import UTC, datetime

from app.config import DEFAULT_CATALOG_DIR, DEFAULT_MISSIONS_DIR
from app.domain.analysis.orchestrator import (
    ENGINE_VERSION,
    analyze_mission,
    scenario_inputs_from_template,
)
from app.domain.analysis.trade import TRADE_METRICS, compute_deltas
from app.domain.catalog.loader import load_catalog
from app.domain.mission.defaults import default_mission_state, list_templates
from app.schemas.analysis import MissionAnalysis
from app.schemas.mission import MissionState

NOW = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)
CATALOG = load_catalog(DEFAULT_CATALOG_DIR)
TEMPLATE = next(
    t for t in list_templates(DEFAULT_MISSIONS_DIR) if t.scenario_id == "neo-rendezvous"
)


def _state() -> MissionState:
    return default_mission_state(
        "neo-rendezvous", mission_id="trade", seed=1, now=NOW, templates_dir=DEFAULT_MISSIONS_DIR
    )


def _analyze(state: MissionState) -> MissionAnalysis:
    return analyze_mission(
        state,
        CATALOG,
        scenario=scenario_inputs_from_template(TEMPLATE),
        engine_version=ENGINE_VERSION,
        now=NOW,
    )


def _with_arch(state: MissionState, **changes: object) -> MissionState:
    data = state.model_dump(by_alias=True)
    data["architecture"].update(changes)
    return MissionState.model_validate(data)


def test_identical_designs_have_zero_deltas_for_every_metric() -> None:
    a = _analyze(_state())
    deltas = compute_deltas(a, a)
    assert set(deltas) == {m.key for m in TRADE_METRICS}
    assert all(v == 0.0 for v in deltas.values())


def test_deltas_are_alternative_minus_base() -> None:
    base = _analyze(_state())
    alt = _analyze(_with_arch(_state(), communicationsId="comms-xband-medium"))
    d = compute_deltas(base, alt)
    assert d["dry_mass_kg"] == alt.budgets.dry_mass_kg.value - base.budgets.dry_mass_kg.value
    assert d["wet_mass_kg"] == alt.budgets.wet_mass_kg.value - base.budgets.wet_mass_kg.value
    assert d["estimated_cost_usd"] == (
        alt.budgets.estimated_cost_usd.value - base.budgets.estimated_cost_usd.value
    )
    assert d["peak_power_w"] == alt.budgets.peak_power_w.value - base.budgets.peak_power_w.value
    assert d["data_downlinked_bit"] == (
        alt.budgets.data_downlinked_bits.value - base.budgets.data_downlinked_bits.value
    )
    assert d["delta_v_margin_km_per_s"] == (
        alt.budgets.delta_v_margin_km_per_s - base.budgets.delta_v_margin_km_per_s
    )
    assert d["total_score"] == alt.score.total - base.score.total
    assert d["science_coverage_score"] == (alt.science.coverage_score - base.science.coverage_score)
    # the swap changes something real
    assert any(v != 0.0 for v in d.values())
    # reversing flips the sign
    back = compute_deltas(alt, base)
    assert all(math.isclose(back[k], -d[k], abs_tol=1e-9) for k in d)


def test_all_deltas_are_finite() -> None:
    base = _analyze(_state())
    alt = _analyze(_with_arch(_state(), communicationsId="comms-xband-medium"))
    assert all(math.isfinite(v) for v in compute_deltas(base, alt).values())


def test_failed_analysis_placeholders_are_omitted_not_zero() -> None:
    base = _analyze(_state())
    failed = _analyze(_with_arch(_state(), communicationsId="comms-does-not-exist"))
    assert any(c.id == "catalog-item-not-found" for c in failed.constraints)
    assert compute_deltas(base, failed) == {}
    assert compute_deltas(failed, base) == {}


def test_inputs_are_not_mutated() -> None:
    state = _state()
    before = state.model_dump_json()
    base = _analyze(state)
    base_json = base.model_dump_json()
    compute_deltas(base, _analyze(_with_arch(state, communicationsId="comms-xband-medium")))
    assert state.model_dump_json() == before
    assert base.model_dump_json() == base_json


def test_none_margin_is_omitted_not_zero_r38() -> None:
    base = _analyze(_state())
    dump = base.model_dump()
    dump["budgets"]["delta_v_margin_km_per_s"] = None
    undefined = MissionAnalysis.model_validate(dump)
    d = compute_deltas(base, undefined)
    assert "delta_v_margin_km_per_s" not in d
    assert "dry_mass_kg" in d
