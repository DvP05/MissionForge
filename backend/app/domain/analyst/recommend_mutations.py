"""One-step mutations over the existing engine, ranked by transparent rules (19.8).

Ranking (best first): fewer failed hard constraints, then fewer warnings, then a higher
mission score, then a smaller cost increase, then id. A mutation is only recommended if it
is strictly better on that order and raises no new hard failure. At most one
recommendation per part slot keeps the list varied.

Confidence: "high" when it clears a hard failure without adding any warning; "medium"
for any other improvement of at least 2 score points; otherwise "low".
"""

from collections.abc import Sequence
from datetime import datetime

from app.domain.analysis.orchestrator import ScenarioInputs, analyze_mission
from app.domain.catalog.loader import Catalog
from app.domain.errors import DomainValidationError
from app.domain.optimization.generate_candidates import (
    SINGLE_FIELDS,
    Change,
    candidate_id,
    single_changes,
)
from app.schemas.analysis import MissionAnalysis
from app.schemas.analyst import DesignMutation, Recommendation
from app.schemas.mission import MissionState

MAX_RECOMMENDATIONS = 5
_FIELD = dict(SINGLE_FIELDS)
_CAMEL = {
    "launch_vehicle_id": "launchVehicleId",
    "bus_id": "busId",
    "propulsion_id": "propulsionId",
    "power_id": "powerId",
    "adcs_id": "adcsId",
    "communications_id": "communicationsId",
    "thermal_id": "thermalId",
    "cdh_id": "cdhId",
    "ground_segment_id": "groundSegmentId",
}


def _metrics(a: MissionAnalysis) -> dict[str, float]:
    return {
        "scoreTotal": a.score.total,
        "scienceCoverageScore": a.science.coverage_score,
        "returnedFraction": a.science.returned_fraction,
        "estimatedCostUsd": float(a.budgets.estimated_cost_usd.value),
        "dryMassKg": float(a.budgets.dry_mass_kg.value),
        "failedConstraints": float(sum(c.status == "fail" for c in a.constraints)),
        "warningConstraints": float(sum(c.status == "warning" for c in a.constraints)),
    }


def _rank(m: dict[str, float]) -> tuple[float, float, float]:
    return (m["failedConstraints"], m["warningConstraints"], -m["scoreTotal"])


def _mutation(ch: Change, catalog: Catalog) -> DesignMutation:
    def name(cid: str | None) -> str:
        comp = catalog.get(cid) if cid else None
        return comp.name if comp else str(cid)

    if ch.category == "instrument" and ch.from_id is None:
        return DesignMutation(
            kind="add-instrument", target="architecture.instrumentIds", to_value=ch.to_id,
            description=f"Add {name(ch.to_id)}",
        )  # fmt: skip
    if ch.category == "instrument" and ch.to_id is None:
        return DesignMutation(
            kind="remove-instrument", target="architecture.instrumentIds", from_value=ch.from_id,
            description=f"Remove {name(ch.from_id)}",
        )  # fmt: skip
    target = (
        "architecture.instrumentIds"
        if ch.category == "instrument"
        else f"architecture.{_CAMEL[_FIELD[ch.category]]}"
    )
    return DesignMutation(
        kind="swap-component", target=target, from_value=ch.from_id, to_value=ch.to_id,
        description=f"Swap {name(ch.from_id)} for {name(ch.to_id)}",
    )  # fmt: skip


def _slot(m: DesignMutation) -> str:
    return (
        m.target
        if m.kind == "swap-component" and m.target != "architecture.instrumentIds"
        else (f"instrument:{m.from_value or m.to_value}")
    )


def apply_mutation(state: MissionState, mutation: DesignMutation) -> MissionState:
    """Apply an allow-listed mutation and bump design_revision. Never evaluates `target`."""
    arch = state.architecture
    if mutation.target == "architecture.instrumentIds":
        ids = list(arch.instrument_ids)
        if mutation.kind in ("remove-instrument", "swap-component") and mutation.from_value:
            ids = [i for i in ids if i != mutation.from_value]
        if mutation.kind in ("add-instrument", "swap-component") and mutation.to_value:
            if mutation.to_value not in ids:
                ids.append(str(mutation.to_value))
        new_arch = arch.model_copy(update={"instrument_ids": tuple(ids)})
    else:
        fields = {f"architecture.{camel}": snake for snake, camel in _CAMEL.items()}
        field = fields.get(mutation.target)
        if (
            mutation.kind != "swap-component"
            or field is None
            or not isinstance(mutation.to_value, str)
        ):
            raise DomainValidationError(
                "MUTATION_NOT_ALLOWED",
                "mutation",
                f"mutation target {mutation.target!r} not allowed",
            )
        new_arch = arch.model_copy(update={field: mutation.to_value})
    return state.model_copy(
        update={"architecture": new_arch, "design_revision": state.design_revision + 1}
    )


def _tradeoffs(
    before: dict[str, float], after: dict[str, float], b: MissionAnalysis, a: MissionAnalysis
) -> list[str]:
    out: list[str] = []
    dc = after["estimatedCostUsd"] - before["estimatedCostUsd"]
    if dc > 0:
        out.append(f"Estimated cost rises by {dc / 1e6:.2f} M USD.")
    dm = after["dryMassKg"] - before["dryMassKg"]
    if dm > 0:
        out.append(f"Dry mass rises by {dm:.1f} kg.")
    ds = after["scienceCoverageScore"] - before["scienceCoverageScore"]
    if ds < 0:
        out.append(f"Science coverage drops by {-ds:.1f} points.")
    old = {c.id: c.status for c in b.constraints}
    for c in a.constraints:
        if c.status == "warning" and old.get(c.id) not in ("warning", "fail"):
            out.append(f"New watch item: {c.label}.")
    return out


def recommend(
    state: MissionState,
    analysis: MissionAnalysis,
    catalog: Catalog,
    *,
    scenario: ScenarioInputs,
    engine_version: str,
    now: datetime,
    max_n: int = 3,
) -> list[Recommendation]:
    """Up to `max_n` improving single changes; [] when nothing nearby is strictly better."""
    if not 1 <= max_n <= MAX_RECOMMENDATIONS:
        raise DomainValidationError(
            "INVALID_COUNT", "maxN", f"max_n must be 1..{MAX_RECOMMENDATIONS}"
        )
    before = _metrics(analysis)
    scored: list[tuple[tuple[float, ...], Recommendation]] = []
    for ch in single_changes(state, catalog):
        mutation = _mutation(ch, catalog)
        candidate = apply_mutation(state, mutation)
        after_analysis = analyze_mission(
            candidate, catalog, scenario=scenario, engine_version=engine_version, now=now
        )
        after = _metrics(after_analysis)
        if not _rank(after) < _rank(before):
            continue
        if after["failedConstraints"] > before["failedConstraints"]:
            continue
        old = {c.id: c.status for c in analysis.constraints}
        cleared = [
            c.id
            for c in after_analysis.constraints
            if old.get(c.id) == "fail" and c.status != "fail"
        ]
        improved = [
            c.id
            for c in after_analysis.constraints
            if old.get(c.id) == "warning" and c.status == "pass"
        ]
        tradeoffs = _tradeoffs(before, after, analysis, after_analysis)
        new_warnings = any(t.startswith("New watch item") for t in tradeoffs)
        gain = after["scoreTotal"] - before["scoreTotal"]
        if cleared and not new_warnings:
            confidence = "high"
        elif gain >= 2.0 or cleared or improved:
            confidence = "medium"
        else:
            confidence = "low"
        labels = {c.id: c.label for c in after_analysis.constraints}
        fixes = [labels[c] for c in cleared + improved]
        explanation = (
            f"{mutation.description}: "
            + (f"clears {', '.join(fixes)}; " if fixes else "")
            + f"mission score {before['scoreTotal']:.1f} to {after['scoreTotal']:.1f}."
        )
        rec = Recommendation(
            id=f"rec-{candidate_id(candidate.architecture)}",
            mutation=mutation,
            metric_before=before,
            metric_after=after,
            tradeoffs=tradeoffs,
            confidence_label=confidence,
            source_refs=cleared + improved,
            explanation=explanation,
        )
        key = (*_rank(after), after["estimatedCostUsd"] - before["estimatedCostUsd"])
        scored.append((key, rec))
    scored.sort(key=lambda kv: (kv[0], kv[1].id))
    picked: list[Recommendation] = []
    slots: set[str] = set()
    for _, rec in scored:
        slot = _slot(rec.mutation)
        if slot in slots:
            continue
        slots.add(slot)
        picked.append(rec)
        if len(picked) == max_n:
            break
    return picked


def recommendations_are_consistent(recs: Sequence[Recommendation]) -> bool:
    """Every recommendation is an allow-listed kind (used by tests and the route)."""
    return all(
        r.mutation.kind in ("swap-component", "add-instrument", "remove-instrument") for r in recs
    )
