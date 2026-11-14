import math

import pytest

from app.domain.analysis.data import DataLedger
from app.domain.analysis.science import (
    DEFAULT_REQUIRED_HOURS,
    missing_reasons,
    pointing_ok_for,
    science_assumptions,
    science_coverage,
)
from app.domain.errors import DomainValidationError
from app.schemas.catalog import CatalogComponent
from app.schemas.mission import MeasurementRequirement, ObservationPlanItem, ScienceObjective
from app.schemas.units import Provenance, Quantity

PROV = Provenance(fidelity="gameplay-estimate", source_name="test")


def q(v: float, unit: str) -> Quantity:
    return Quantity(value=v, unit=unit, provenance=PROV)  # type: ignore[arg-type]


def inst(caps: list[str], pointing: float = 1.0, cid: str = "i1") -> CatalogComponent:
    return CatalogComponent(
        id=cid, name=cid, category="instrument", description="d",
        parameters={"pointing_requirement": q(pointing, "deg")},
        capabilities=caps, source_record_id="r", provenance=PROV,
    )  # fmt: skip


def req(
    rid: str = "m1", cap: str = "imaging", w: float = 1.0, required: bool = True,
    thr: Quantity | None = None,
) -> MeasurementRequirement:
    return MeasurementRequirement(
        id=rid, description="d", instrument_capability=cap, coverage_weight=w,
        required=required, target_threshold=thr,
    )  # fmt: skip


def obj(reqs: list[MeasurementRequirement], oid: str = "o1", prio: float = 1.0) -> ScienceObjective:
    return ScienceObjective(
        id=oid, title=oid, question="?", priority=prio, required_measurements=tuple(reqs)
    )


def plan(mid: str = "m1", hours: float = 1.0, duty: float = 1.0) -> ObservationPlanItem:
    return ObservationPlanItem(
        measurement_id=mid, start_day=0, duration_hours=hours, duty_cycle=duty
    )


def ledger(gen: float = 100.0, down: float = 100.0) -> DataLedger:
    return DataLedger(
        generated_bits=gen, downlinked_bits=down, buffer_timeline=(), peak_buffer_bits=0.0,
        overflow_bits=0.0, margin_fraction=0.0, per_contact=(),
    )  # fmt: skip


def run(objs, insts, items, led=None, point=0.5, power=True, **kw):  # type: ignore[no-untyped-def]
    return science_coverage(
        objs, insts, items, led or ledger(), pointing_accuracy_deg=point, power_ok=power, **kw
    )


def test_full_coverage() -> None:
    r = run([obj([req()])], [inst(["imaging"])], [plan()])
    assert r.coverage_score == pytest.approx(100.0)
    assert r.weighted_objective_coverage == {"o1": pytest.approx(1.0)}
    assert r.missing_requirements == []
    assert r.collected_fraction == pytest.approx(1.0)
    assert r.returned_fraction == pytest.approx(1.0)


def test_missing_capability_contributes_zero() -> None:
    r = run([obj([req()])], [inst(["spectroscopy"])], [plan()])
    assert r.coverage_score == 0.0
    assert r.missing_requirements == ["m1"]
    reasons = missing_reasons(
        [obj([req()])], [inst(["spectroscopy"])], [plan()], ledger(),
        pointing_accuracy_deg=0.5, power_ok=True,
    )  # fmt: skip
    assert reasons["m1"] == "no-capability"


def test_objective_weighted_mean_and_priority_score() -> None:
    o1 = obj([req("a", "imaging", 3.0), req("b", "mag", 1.0)], "o1", 3.0)
    o2 = obj([req("c", "imaging", 1.0)], "o2", 1.0)
    r = run([o1, o2], [inst(["imaging"])], [plan("a"), plan("c", 0.5)])
    # o1 = (3*1 + 1*0)/4 = .75 ; o2 = .5 ; score = 100*(3*.75+1*.5)/4
    assert r.weighted_objective_coverage["o1"] == pytest.approx(0.75)
    assert r.weighted_objective_coverage["o2"] == pytest.approx(0.5)
    assert r.coverage_score == pytest.approx(100 * (3 * 0.75 + 0.5) / 4)
    assert r.missing_requirements == ["b"]


def test_no_instruments_scores_zero_all_required_missing() -> None:
    o = obj([req("a"), req("b", required=False), req("c")])
    r = run([o], [], [plan("a"), plan("c")])
    assert r.coverage_score == 0.0
    assert r.missing_requirements == ["a", "c"]
    assert r.collected_fraction == 0.0 and r.returned_fraction == 0.0


def test_collected_but_not_downlinked_lowers_returned_only() -> None:
    full = run([obj([req()])], [inst(["imaging"])], [plan()], ledger(100, 100))
    half = run([obj([req()])], [inst(["imaging"])], [plan()], ledger(100, 40))
    assert half.collected_fraction == full.collected_fraction == pytest.approx(1.0)
    assert half.returned_fraction == pytest.approx(0.4)
    assert half.coverage_score == pytest.approx(40.0)


def test_nothing_returned_marks_required_missing() -> None:
    r = run([obj([req()])], [inst(["imaging"])], [plan()], ledger(100, 0))
    assert r.collected_fraction == pytest.approx(1.0)
    assert r.missing_requirements == ["m1"]
    reasons = missing_reasons([obj([req()])], [inst(["imaging"])], [plan()], ledger(100, 0),
                              pointing_accuracy_deg=0.5, power_ok=True)  # fmt: skip
    assert reasons["m1"] == "no-returned-data"


def test_zero_generated_is_zero_not_nan() -> None:
    r = run([obj([req()])], [inst(["imaging"])], [plan()], ledger(0, 0))
    assert r.returned_fraction == 0.0 and not math.isnan(r.coverage_score)


def test_schedule_fraction_and_duty_cycle() -> None:
    r = run([obj([req()])], [inst(["imaging"])], [plan(hours=2.0, duty=0.25)])
    assert r.collected_fraction == pytest.approx(0.5)  # 0.5 h of 1 h default
    r2 = run([obj([req()])], [inst(["imaging"])], [plan(hours=10.0)])
    assert r2.collected_fraction == pytest.approx(1.0)  # capped


def test_required_hours_from_threshold_and_mapping() -> None:
    o = obj([req(thr=q(2.0, "day"))])  # 48 h
    r = run([o], [inst(["imaging"])], [plan(hours=24.0)])
    assert r.collected_fraction == pytest.approx(0.5)
    o2 = obj([req(thr=q(7200.0, "s"))])  # 2 h
    r2 = run([o2], [inst(["imaging"])], [plan(hours=1.0)])
    assert r2.collected_fraction == pytest.approx(0.5)
    r3 = run([obj([req()])], [inst(["imaging"])], [plan(hours=1.0)],
             required_hours_by_measurement={"m1": 4.0})  # fmt: skip
    assert r3.collected_fraction == pytest.approx(0.25)
    assert DEFAULT_REQUIRED_HOURS == 1.0


def test_pointing_gate_best_instrument() -> None:
    tight = inst(["imaging"], 0.05, "tight")
    loose = inst(["imaging"], 1.0, "loose")
    ok = run([obj([req()])], [tight, loose], [plan()], point=0.5)
    assert ok.collected_fraction == pytest.approx(1.0)  # loose meets it
    bad = run([obj([req()])], [tight], [plan()], point=0.5)
    assert bad.collected_fraction == 0.0 and bad.missing_requirements == ["m1"]


def test_power_not_ok_hard_zero() -> None:
    r = run([obj([req()])], [inst(["imaging"])], [plan()], power=False)
    assert r.coverage_score == 0.0 and r.missing_requirements == ["m1"]


def test_unscheduled_required_is_missing() -> None:
    r = run([obj([req()])], [inst(["imaging"])], [])
    assert r.missing_requirements == ["m1"]


def test_zero_weight_sum_is_validation_error() -> None:
    with pytest.raises(DomainValidationError):
        run([obj([req(w=0.0)])], [inst(["imaging"])], [plan()])


def test_empty_objectives() -> None:
    r = run([], [inst(["imaging"])], [])
    assert r.coverage_score == 0.0 and r.weighted_objective_coverage == {}


def test_assumptions_document_estimates() -> None:
    text = " ".join(science_assumptions())
    assert "1.0 h" in text and "gameplay-estimate" in text and "power" in text


def test_assigned_instrument_controls_pointing() -> None:
    tight, loose = inst(["imaging"], 0.05, "tight"), inst(["imaging"], 1.0, "loose")
    objs = [obj([req()])]
    # default rule credits the loosest matching instrument
    assert run(objs, [tight, loose], [plan()]).coverage_score == pytest.approx(100.0)
    assert pointing_ok_for(objs, [tight, loose], pointing_accuracy_deg=0.5) is True
    # with the engine's assignment only the assigned instrument is checked
    assigned = {"m1": tight}
    r = run(objs, [tight, loose], [plan()], instrument_by_measurement=assigned)
    assert r.coverage_score == 0.0
    assert missing_reasons(
        objs, [tight, loose], [plan()], ledger(), pointing_accuracy_deg=0.5, power_ok=True,
        instrument_by_measurement=assigned,
    ) == {"m1": "no-returned-data"}  # fmt: skip
    assert (
        pointing_ok_for(
            objs, [tight, loose], pointing_accuracy_deg=0.5, instrument_by_measurement=assigned
        )
        is False
    )


def test_pointing_ok_counts_only_required_capable_measurements() -> None:
    tight = inst(["imaging"], 0.05, "tight")
    optional = [obj([req(required=False), req("m2", cap="none")])]
    assert pointing_ok_for(optional, [tight], pointing_accuracy_deg=0.5) is True
    assert pointing_ok_for([obj([req()])], [tight], pointing_accuracy_deg=0.5) is False
    with pytest.raises(DomainValidationError):
        pointing_ok_for([], [], pointing_accuracy_deg=math.inf)
