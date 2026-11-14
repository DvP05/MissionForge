"""Explain the effect of one design edit (architecture 19.1 behaviour 7)."""

import math
from collections.abc import Iterator

from app.schemas.analysis import MissionAnalysis
from app.schemas.optimization import ArchitectureGraph, ImpactReport, MetricChange

# pass and not-modelled are not violations; warning < fail.
_RANK: dict[str, int] = {"pass": 0, "not-modelled": 0, "warning": 1, "fail": 2}


def _metrics(a: MissionAnalysis) -> Iterator[tuple[str, float | None, str]]:
    b = a.budgets
    for name, quantity in (
        ("dryMassKg", b.dry_mass_kg),
        ("propellantMassKg", b.propellant_mass_kg),
        ("wetMassKg", b.wet_mass_kg),
        ("averagePowerW", b.average_power_w),
        ("peakPowerW", b.peak_power_w),
        ("dataGeneratedBits", b.data_generated_bits),
        ("dataDownlinkedBits", b.data_downlinked_bits),
        ("requiredDeltaVKmPerS", b.required_delta_v_km_per_s),
        ("availableDeltaVKmPerS", b.available_delta_v_km_per_s),
        ("estimatedCostUsd", b.estimated_cost_usd),
    ):
        yield name, float(quantity.value), quantity.unit
    yield "massMarginFraction", b.mass_margin_fraction, "fraction"
    yield "energyMarginFraction", b.energy_margin_fraction, "fraction"
    yield "dataMarginFraction", b.data_margin_fraction, "fraction"
    yield "deltaVMarginKmPerS", b.delta_v_margin_km_per_s, "km/s"
    yield "scienceCoverageScore", a.science.coverage_score, "points"
    yield "collectedFraction", a.science.collected_fraction, "fraction"
    yield "returnedFraction", a.science.returned_fraction, "fraction"
    yield "nominalReliability", a.reliability.nominal_reliability, "fraction"
    yield "scoreTotal", a.score.total, "points"


def _changed(x: float | None, y: float | None) -> bool:
    """A metric that becomes defined or undefined (R38 None) counts as changed."""
    if x is None or y is None:
        return (x is None) != (y is None)
    return not math.isclose(x, y, rel_tol=1e-12, abs_tol=1e-12)


def _statuses(graph: ArchitectureGraph) -> dict[str, str]:
    """Requirement/objective entity id -> coverage status attribute."""
    out: dict[str, str] = {}
    for n in graph.nodes:
        status = n.attributes.get("status")
        if n.kind in ("measurement-requirement", "science-objective") and n.entity_id:
            out[n.entity_id] = status if isinstance(status, str) else ""
    return out


def trace_impact(
    before: MissionAnalysis,
    after: MissionAnalysis,
    graph: ArchitectureGraph,
    *,
    before_graph: ArchitectureGraph | None = None,
) -> ImpactReport:
    """Changed metrics, newly violated / improved constraints and affected objectives.

    `graph` is the graph of the edited revision; it supplies requirement -> objective
    links. With `before_graph`, a requirement whose coverage status changed (for example
    "not-returned" -> "uncovered" after removing its only instrument) also marks its
    objective as affected, even when the numeric coverage was already zero.
    """
    after_metrics = {name: (value, unit) for name, value, unit in _metrics(after)}
    changed = [
        MetricChange(metric=name, before=value, after=after_metrics[name][0], unit=unit)
        for name, value, unit in _metrics(before)
        if _changed(value, after_metrics[name][0])
    ]

    rank_before = {c.id: _RANK[c.status] for c in before.constraints}
    rank_after = {c.id: _RANK[c.status] for c in after.constraints}
    ids = list(rank_after) + [cid for cid in rank_before if cid not in rank_after]

    def before_rank(cid: str) -> int:
        return rank_before.get(cid, 0)

    def after_rank(cid: str) -> int:
        return rank_after.get(cid, 0)

    newly_violated = [c for c in ids if after_rank(c) >= 1 and after_rank(c) > before_rank(c)]
    improved = [c for c in ids if before_rank(c) >= 1 and after_rank(c) < before_rank(c)]

    affected: set[str] = set()
    cov_b = before.science.weighted_objective_coverage
    cov_a = after.science.weighted_objective_coverage
    for obj_id in set(cov_b) | set(cov_a):
        if obj_id not in cov_b or obj_id not in cov_a or _changed(cov_b[obj_id], cov_a[obj_id]):
            affected.add(obj_id)
    flipped = set(before.science.missing_requirements) ^ set(after.science.missing_requirements)
    if before_graph is not None:
        old, new = _statuses(before_graph), _statuses(graph)
        flipped |= {eid for eid in set(old) | set(new) if old.get(eid) != new.get(eid)}
        objective_ids = {n.entity_id for n in graph.nodes if n.kind == "science-objective"}
        affected |= {eid for eid in flipped if eid in objective_ids}
    entity = {n.id: n.entity_id for n in graph.nodes}
    for e in graph.edges:
        if (
            e.kind == "satisfies"
            and e.from_id.startswith("requirement:")
            and e.to_id.startswith("objective:")
            and entity.get(e.from_id) in flipped
        ):
            obj_entity = entity.get(e.to_id)
            if obj_entity is not None:
                affected.add(obj_entity)

    order = [n.entity_id for n in graph.nodes if n.kind == "science-objective" and n.entity_id]
    ordered = [o for o in order if o in affected] + sorted(affected - set(order))
    return ImpactReport(
        changed_metrics=changed,
        newly_violated=newly_violated,
        improved=improved,
        affected_objectives=ordered,
    )
