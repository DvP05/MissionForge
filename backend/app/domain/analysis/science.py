"""Science coverage (architecture section 7.10). Pure, deterministic.

Per measurement requirement::

    collected = capability_match x min(1, scheduled_h / required_h) x pointing_ok x power_ok
    returned  = collected x returned_fraction

* capability_match: 1 if any selected instrument lists the requirement's capability, else 0.
* pointing_ok: 1 if the ADCS accuracy (deg) is <= the pointing requirement of at least one
  capability-matching instrument (the loosest-requirement matching instrument is credited),
  else 0. Instruments without a pointing_requirement are not gated.
* power_ok False is a hard zero for every requirement.
* scheduled_h = sum(duration_hours x duty_cycle) over plan items with that measurement id.
* returned_fraction = downlinked / generated bits from the data ledger (0 if nothing generated).

Objective coverage = sum(w x returned) / sum(w). ``coverage_score`` (0..100) =
100 x sum(priority x coverage) / sum(priority): science counts RETURNED data only.
Mission-level ``collected_fraction`` / ``returned_fraction`` are the priority-weighted
objective coverages computed from the collected / returned achieved fractions.
"""

from collections.abc import Mapping, Sequence

from app.domain.analysis.data import DataLedger
from app.domain.errors import DomainValidationError
from app.domain.units.conversions import day_to_s
from app.domain.units.guards import require_finite
from app.schemas.analysis import ScienceAnalysis
from app.schemas.catalog import CatalogComponent
from app.schemas.mission import MeasurementRequirement, ObservationPlanItem, ScienceObjective

MODEL_ID = "science-v1"

# gameplay-estimate: hours of scheduled observation needed when a requirement states none.
DEFAULT_REQUIRED_HOURS = 1.0

REASON_NO_CAPABILITY = "no-capability"
REASON_NO_RETURNED_DATA = "no-returned-data"

_ASSUMPTIONS: tuple[str, ...] = (
    "Required observation time defaults to 1.0 h per measurement when neither the requirement "
    "threshold (s or day) nor an explicit mapping gives one (gameplay-estimate).",
    "Capability match is binary: any selected instrument listing the capability counts.",
    "Pointing is binary: ADCS accuracy must be <= the pointing requirement of a matching "
    "instrument; the loosest-requirement matching instrument is credited.",
    "A power shortfall (power_ok false) is a hard zero for all science (gameplay-estimate).",
    "Science score counts RETURNED data: returned fraction = downlinked / generated bits "
    "(0 if nothing was generated); collected-but-not-returned data is reported separately.",
    "Mission-level collected/returned fractions are priority-weighted objective coverages.",
)


def science_assumptions() -> tuple[str, ...]:
    return _ASSUMPTIONS


def _required_hours(r: MeasurementRequirement, mapping: Mapping[str, float] | None) -> float:
    t = r.target_threshold
    if t is not None and t.unit == "s":
        hours = t.value / 3600.0
    elif t is not None and t.unit == "day":
        hours = day_to_s(t.value) / 3600.0
    elif mapping is not None and r.id in mapping:
        hours = require_finite(mapping[r.id], f"required_hours[{r.id}]")
    else:
        hours = DEFAULT_REQUIRED_HOURS
    if hours <= 0:
        raise DomainValidationError(
            "NON_POSITIVE_REQUIRED_HOURS", f"required_hours[{r.id}]", "must be > 0"
        )
    return hours


def _matches(
    r: MeasurementRequirement, instruments: Sequence[CatalogComponent]
) -> list[CatalogComponent]:
    return [i for i in instruments if r.instrument_capability in i.capabilities]


def _pointing_ok(matching: Sequence[CatalogComponent], accuracy_deg: float) -> float:
    for i in matching:
        p = i.parameters.get("pointing_requirement")
        if p is None or accuracy_deg <= p.value:
            return 1.0
    return 0.0


def _returned_fraction(ledger: DataLedger) -> float:
    if ledger.generated_bits <= 0:
        return 0.0
    return min(1.0, max(0.0, ledger.downlinked_bits / ledger.generated_bits))


def _scheduled_hours(plan: Sequence[ObservationPlanItem]) -> dict[str, float]:
    out: dict[str, float] = {}
    for it in plan:
        out[it.measurement_id] = out.get(it.measurement_id, 0.0) + it.duration_hours * it.duty_cycle
    return out


def _collected(
    r: MeasurementRequirement,
    instruments: Sequence[CatalogComponent],
    sched: Mapping[str, float],
    pointing_accuracy_deg: float,
    power_ok: bool,
    mapping: Mapping[str, float] | None,
) -> tuple[float, float]:
    """Return (capability_match, collected achieved fraction)."""
    matching = _matches(r, instruments)
    capability = 1.0 if matching else 0.0
    if not power_ok or not matching:
        return capability, 0.0
    frac = min(1.0, sched.get(r.id, 0.0) / _required_hours(r, mapping))
    return capability, capability * frac * _pointing_ok(matching, pointing_accuracy_deg)


def _validate(objectives: Sequence[ScienceObjective]) -> None:
    for o in objectives:
        if sum(r.coverage_weight for r in o.required_measurements) <= 0:
            raise DomainValidationError(
                "ZERO_COVERAGE_WEIGHT", f"objective[{o.id}]", "sum of coverage weights must be > 0"
            )
    if objectives and sum(o.priority for o in objectives) <= 0:
        raise DomainValidationError("ZERO_PRIORITY", "objectives", "sum of priorities must be > 0")


def missing_reasons(
    objectives: Sequence[ScienceObjective],
    instruments: Sequence[CatalogComponent],
    observation_plan: Sequence[ObservationPlanItem],
    data_ledger: DataLedger,
    *,
    pointing_accuracy_deg: float,
    power_ok: bool,
    required_hours_by_measurement: Mapping[str, float] | None = None,
) -> dict[str, str]:
    """Required measurement id -> reason: 'no-capability' or 'no-returned-data'."""
    _validate(objectives)
    sched = _scheduled_hours(observation_plan)
    ret = _returned_fraction(data_ledger)
    out: dict[str, str] = {}
    for o in objectives:
        for r in o.required_measurements:
            if not r.required:
                continue
            cap, col = _collected(
                r, instruments, sched, pointing_accuracy_deg, power_ok,
                required_hours_by_measurement,
            )  # fmt: skip
            if cap == 0.0:
                out[r.id] = REASON_NO_CAPABILITY
            elif col * ret == 0.0:
                out[r.id] = REASON_NO_RETURNED_DATA
    return out


def science_coverage(
    objectives: Sequence[ScienceObjective],
    instruments: Sequence[CatalogComponent],
    observation_plan: Sequence[ObservationPlanItem],
    data_ledger: DataLedger,
    *,
    pointing_accuracy_deg: float,
    power_ok: bool,
    required_hours_by_measurement: Mapping[str, float] | None = None,
) -> ScienceAnalysis:
    require_finite(pointing_accuracy_deg, "pointing_accuracy_deg")
    _validate(objectives)
    sched = _scheduled_hours(observation_plan)
    ret = _returned_fraction(data_ledger)
    obj_returned: dict[str, float] = {}
    obj_collected: dict[str, float] = {}
    for o in objectives:
        wsum = sum(r.coverage_weight for r in o.required_measurements)
        col_w = 0.0
        for r in o.required_measurements:
            _, col = _collected(
                r, instruments, sched, pointing_accuracy_deg, power_ok,
                required_hours_by_measurement,
            )  # fmt: skip
            col_w += r.coverage_weight * col
        obj_collected[o.id] = col_w / wsum
        obj_returned[o.id] = col_w * ret / wsum

    psum = sum(o.priority for o in objectives)

    def mission(vals: Mapping[str, float]) -> float:
        if psum <= 0:
            return 0.0
        return min(1.0, max(0.0, sum(o.priority * vals[o.id] for o in objectives) / psum))

    returned = mission(obj_returned)
    return ScienceAnalysis(
        coverage_score=100.0 * returned,
        weighted_objective_coverage={k: min(1.0, max(0.0, v)) for k, v in obj_returned.items()},
        missing_requirements=list(
            missing_reasons(
                objectives, instruments, observation_plan, data_ledger,
                pointing_accuracy_deg=pointing_accuracy_deg, power_ok=power_ok,
                required_hours_by_measurement=required_hours_by_measurement,
            )
        ),
        collected_fraction=mission(obj_collected),
        returned_fraction=returned,
    )  # fmt: skip
