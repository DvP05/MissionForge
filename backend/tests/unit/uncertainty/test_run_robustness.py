"""run_robustness and the allow-listed paths (Task 6.3, architecture 19.3)."""

import time

import pytest

from app.domain.errors import DomainValidationError
from app.domain.uncertainty import (
    ALLOWED_PATHS,
    DISCLAIMER,
    MAX_SAMPLES,
    RobustnessLimitExceeded,
    apply_samples,
    run_robustness,
)
from app.schemas.uncertainty import RobustnessResult, UncertaintyProfile
from app.services.robustness_service import load_profile
from app.services.template_service import TemplateService

from ..architecture_graph._support import NOW, catalog, edit_arch, state

SCENARIOS = TemplateService.from_directory()


def _run(
    s=None, n: int = 40, seed: int = 42, profile: UncertaintyProfile | None = None
) -> RobustnessResult:  # type: ignore[no-untyped-def]
    s = s or state()
    return run_robustness(
        s,
        profile or load_profile(),
        catalog(),
        scenario=SCENARIOS.scenario_inputs(s.scenario_id),  # type: ignore[arg-type]
        n=n,
        seed=seed,
        engine_version="0.1.0",
        now=NOW,
    )


def _fixed():  # type: ignore[no-untyped-def]
    return edit_arch(state(), communications_id="comms-xband-medium")


def test_default_profile_uses_only_allowed_paths() -> None:
    profile = load_profile()
    assert profile.parameters
    assert all(p.path in ALLOWED_PATHS for p in profile.parameters)
    assert all("gameplay-estimate" in p.rationale for p in profile.parameters)


def test_same_seed_is_identical_and_other_seed_differs() -> None:
    a, b = _run(_fixed(), seed=7), _run(_fixed(), seed=7)
    assert a.model_dump_json() == b.model_dump_json()
    c = _run(_fixed(), seed=8)
    assert c.metrics["wetMassKg"] != a.metrics["wetMassKg"]


def test_input_state_and_catalog_unchanged() -> None:
    s = _fixed()
    before_state = s.model_dump_json()
    before_power = catalog()[s.architecture.power_id].model_dump_json()
    _run(s, n=10)
    assert s.model_dump_json() == before_state
    assert catalog()[s.architecture.power_id].model_dump_json() == before_power


def test_result_shape_and_honesty_labels() -> None:
    r = _run(_fixed())
    assert r.samples == 40 and r.seed == 42
    assert r.profile_version == "default@0.1.0"
    assert r.disclaimer == DISCLAIMER and "not a flight-qualified" in r.disclaimer
    assert any("epistemic" in a for a in r.assumptions)
    lo, hi = r.feasibility_wilson_95
    assert 0.0 <= lo <= r.probability_feasible <= hi <= 1.0
    for q in r.metrics.values():
        assert q.p10 <= q.median <= q.p90


def test_starter_design_fails_link_margin_in_every_sample() -> None:
    r = _run(state())
    assert r.probability_feasible == 0.0
    assert r.feasibility_wilson_95[0] == 0.0 and r.feasibility_wilson_95[1] > 0
    assert r.failure_counts == {"link-margin": 40}


def test_failure_counts_keyed_by_constraint_id() -> None:
    r = _run(state())
    assert all(isinstance(k, str) and k for k in r.failure_counts)


def test_sample_count_limits() -> None:
    with pytest.raises(DomainValidationError):
        _run(n=0)
    with pytest.raises(RobustnessLimitExceeded) as err:
        _run(n=MAX_SAMPLES + 1)
    assert err.value.code == "SIMULATION_LIMIT_EXCEEDED"


def test_path_not_in_allow_list_rejected() -> None:
    bad = UncertaintyProfile.model_validate(
        {
            "id": "bad",
            "version": "1",
            "parameters": [
                {
                    "id": "x",
                    "path": "__class__.__init__",
                    "kind": "aleatory",
                    "distribution": {"kind": "uniform", "min": 0.9, "max": 1.1},
                    "rationale": "attack",
                }
            ],
        }
    )
    with pytest.raises(DomainValidationError) as err:
        _run(profile=bad, n=1)
    assert err.value.code == "UNCERTAIN_PATH_NOT_ALLOWED"


def test_apply_samples_scales_selected_parts_only() -> None:
    s = state()
    out = apply_samples(s, catalog(), {"catalog.power.battery_capacity": 0.5})
    power = s.architecture.power_id
    new_cap = out.catalog[power].parameters["battery_capacity"].value
    assert new_cap == pytest.approx(catalog()[power].parameters["battery_capacity"].value * 0.5)
    other = next(c.id for c in catalog().by_category("power") if c.id != power)
    assert out.catalog[other] == catalog()[other]


def test_fraction_paths_clamp_and_count() -> None:
    s = state()
    out = apply_samples(s, catalog(), {"operations.observation_plan.duty_cycle": 100.0})
    assert all(o.duty_cycle == 1.0 for o in out.state.operations.observation_plan)
    assert out.clamped == len(s.operations.observation_plan)


def test_scale_must_be_positive() -> None:
    with pytest.raises(DomainValidationError):
        apply_samples(state(), catalog(), {"catalog.propulsion.isp": 0.0})


def test_250_samples_under_two_seconds() -> None:
    _run(_fixed(), n=5)
    start = time.perf_counter()
    _run(_fixed(), n=250)
    assert time.perf_counter() - start < 2.0
