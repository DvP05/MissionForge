"""Derive scheduler inputs from a design (Task 6.6). Pure; all values labelled estimates.

- Each observation-plan item becomes one opportunity per capable selected instrument.
  Science value = objective priority x requirement coverage weight. Data = instrument
  data rate x duty cycle x duration. Energy = instrument power x duty cycle x duration.
- An instrument that needs finer pointing than the selected ADCS gives is flagged with the
  "precision-pointing" attitude, which this spacecraft does not support (POINTING).
- Per-observation energy budget = battery capacity x usable depth of discharge.
- Each downlink-plan item becomes a contact: capacity = min(planned rate, radio maximum
  rate) x duration. Its link margin is the engine's worst-case margin for the design.
- Storage capacity = the C&DH storage.
"""

from dataclasses import dataclass

from app.domain.catalog.loader import Catalog
from app.domain.operations.schedule_data_cycles import ScheduleResources
from app.schemas.analysis import MissionAnalysis
from app.schemas.catalog import CatalogComponent
from app.schemas.mission import MissionState
from app.schemas.operations import ContactWindow, ObservationOpportunity

DAY_S = 86400.0
HOUR_S = 3600.0
WH_TO_J = 3600.0


@dataclass(frozen=True)
class ScheduleInputs:
    opportunities: list[ObservationOpportunity]
    contacts: list[ContactWindow]
    resources: ScheduleResources
    measurement_of: dict[str, str]  # opportunity id -> measurement requirement id


def _p(comp: CatalogComponent | None, key: str, default: float = 0.0) -> float:
    if comp is None or key not in comp.parameters:
        return default
    return float(comp.parameters[key].value)


def build_schedule_inputs(
    state: MissionState, analysis: MissionAnalysis, catalog: Catalog
) -> ScheduleInputs:
    arch = state.architecture
    adcs = catalog.get(arch.adcs_id)
    power = catalog.get(arch.power_id)
    comms = catalog.get(arch.communications_id)
    cdh = catalog.get(arch.cdh_id)
    accuracy = _p(adcs, "pointing_accuracy", float("inf"))
    reqs = {
        r.id: (r, o.priority) for o in state.science_objectives for r in o.required_measurements
    }
    instruments = [catalog.get(i) for i in dict.fromkeys(arch.instrument_ids)]

    opportunities: list[ObservationOpportunity] = []
    measurement_of: dict[str, str] = {}
    for idx, item in enumerate(state.operations.observation_plan):
        found = reqs.get(item.measurement_id)
        if found is None:
            continue
        req, priority = found
        start = item.start_day * DAY_S
        duration = item.duration_hours * HOUR_S
        for inst in instruments:
            if inst is None or req.instrument_capability not in inst.capabilities:
                continue
            needs = _p(inst, "pointing_requirement", float("inf"))
            oid = f"obs:{idx}:{inst.id}"
            opportunities.append(
                ObservationOpportunity(
                    id=oid,
                    start=start,
                    end=start + duration,
                    instrument_id=inst.id,
                    expected_science_value=priority * req.coverage_weight,
                    generated_data_bits=_p(inst, "data_rate") * item.duty_cycle * duration,
                    energy_joules=_p(inst, "power_w") * item.duty_cycle * duration,
                    slew_seconds=0.0,
                    compatible_attitude="target-pointing"
                    if accuracy <= needs
                    else "precision-pointing",
                )
            )
            measurement_of[oid] = req.id

    link = next((c for c in analysis.constraints if c.id == "link-margin"), None)
    margin = float(link.actual.value) if link is not None and link.actual is not None else 0.0
    max_rate = _p(comms, "max_data_rate", float("inf"))
    contacts = [
        ContactWindow(
            id=f"contact:{i}",
            start=d.start_day * DAY_S,
            end=d.start_day * DAY_S + d.duration_minutes * 60.0,
            max_downlink_bits=min(d.data_rate_bits_per_second, max_rate)
            * d.duration_minutes
            * 60.0,
            station_id=arch.ground_segment_id,
            link_margin_db=margin,
        )
        for i, d in enumerate(state.operations.downlink_plan)
    ]
    resources = ScheduleResources(
        buffer_capacity_bits=_p(cdh, "storage"),
        max_energy_per_observation_joules=_p(power, "battery_capacity")
        * WH_TO_J
        * _p(power, "usable_dod", 1.0),
        supported_attitudes=frozenset({"target-pointing"}),
    )
    return ScheduleInputs(opportunities, contacts, resources, measurement_of)
