"""Science outcomes and the final report of a run (architecture 9.6, 7.10; AC-12 inputs).

Per-objective science (nominal run):

* ``returned_fraction`` = the analysis ``weighted_objective_coverage`` of the objective
  (science counts RETURNED data only).
* ``collected_fraction`` = returned / ledger return ratio (downlinked / generated bits),
  which inverts ``returned = collected x ratio`` of the science model. When nothing is
  returned the per-objective split is not exposed by ScienceAnalysis, so the mission-level
  ``collected_fraction`` is used for every objective (labelled limitation).
* ``status``: ``achieved`` if returned >= ``ACHIEVED_RETURNED_FRACTION`` x the objective's
  required share (coverage weight of its mandatory measurements / total weight; 1 when it
  has no mandatory measurement), so optional measurements are not needed to achieve it;
  ``partial`` if anything is returned, else ``missed``.

Task 4.2 (as-flown science): the outcomes are computed from the engine's re-analysis of the
as-flown plan (``science`` of that context) and ``returned_scale`` = returned ratio after
buffer losses / as-flown return ratio, so ``returned = coverage x returned_scale`` while the
collected fraction is unchanged by a loss of downlinkable data.

Outcome rule: ``terminated`` when the run ended early (a postmortem report: the root causes
start with the termination cause, the counterfactuals include what the design lacked, and the
review stays available); ``success`` when the design is not infeasible and every objective
is achieved; ``failure`` when no objective returned anything (or there are no objectives);
otherwise ``partial``. ``realized_risks`` lists the failed/warning constraints and then
every anomaly / scenario event that occurred (``"<declared id> (<type>, day d): title"``).
"""

from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.analysis.context import AnalysisContext
from app.domain.simulation.phases import PHASE_ASSUMPTIONS
from app.domain.simulation.telemetry import TELEMETRY_ASSUMPTIONS
from app.schemas.analysis import MissionAnalysis, ScienceAnalysis
from app.schemas.mission import MissionState
from app.schemas.simulation import FinalReport, ScienceOutcome

ACHIEVED_RETURNED_FRACTION = 0.8  # gameplay-estimate threshold

BASE_LIMITATIONS: tuple[str, ...] = (
    "deterministic event simulation; not orbital propagation",
    *PHASE_ASSUMPTIONS,
    *TELEMETRY_ASSUMPTIONS,
)
NOMINAL_LIMITATION = "Nominal run: no anomalies or decisions are injected."
CATALOG_LIMITATION = "All catalogue values are illustrative gameplay-estimate archetypes."
LIMITATIONS: tuple[str, ...] = (*BASE_LIMITATIONS, NOMINAL_LIMITATION, CATALOG_LIMITATION)
EFFECT_LIMITATIONS: tuple[str, ...] = (
    "Anomalies are deterministic rules on the design's own margins; the only randomness is "
    "the day of the declared scenario event, drawn from the seeded scenario stream.",
    "Event effects are gameplay-estimate approximations: skipped observations and missed "
    "contacts are re-analysed by the engine; lost buffer data can no longer be downlinked "
    "(downlinked = min(downlinked, generated - lost)); battery dips recover by the next "
    "checkpoint.",
)
TERMINATION_LIMITATION = (
    "Terminated run: activities from day {day:g} on were cancelled; this postmortem and the "
    "mission review remain available."
)
NO_RETURN_LIMITATION = (
    "Nothing was returned, so each objective's collected fraction is the mission-level "
    "collected fraction (the per-objective split is not exposed by the analysis)."
)


def _clamp01(x: float) -> float:
    return min(1.0, max(0.0, x))


def return_ratio(ctx: AnalysisContext) -> float:
    gen = ctx.data.generated_bits
    return _clamp01(ctx.data.downlinked_bits / gen) if gen > 0.0 else 0.0


def science_outcomes(
    state: MissionState, science: ScienceAnalysis, ratio: float, returned_scale: float = 1.0
) -> tuple[ScienceOutcome, ...]:
    cov = science.weighted_objective_coverage
    out: list[ScienceOutcome] = []
    for o in state.science_objectives:
        flown = _clamp01(cov.get(o.id, 0.0))
        collected = _clamp01(flown / ratio) if ratio > 0.0 else science.collected_fraction
        collected = max(collected, flown)
        returned = _clamp01(flown * returned_scale)
        total_w = sum(r.coverage_weight for r in o.required_measurements)
        req_w = sum(r.coverage_weight for r in o.required_measurements if r.required)
        share = req_w / total_w if total_w > 0.0 and req_w > 0.0 else 1.0
        if returned > 0.0 and returned >= ACHIEVED_RETURNED_FRACTION * share:
            status: str = "achieved"
        elif returned > 0.0:
            status = "partial"
        else:
            status = "missed"
        out.append(
            ScienceOutcome.model_validate(
                {
                    "objective_id": o.id,
                    "collected_fraction": collected,
                    "returned_fraction": returned,
                    "status": status,
                }
            )
        )
    return tuple(out)


@dataclass(frozen=True)
class Incident:
    """An anomaly / scenario event that occurred, for the report."""

    declared_id: str
    event_type: str
    mission_day: float
    title: str
    why: str
    counterfactual: str
    choice_label: str | None = None


@dataclass(frozen=True)
class TerminationInfo:
    mission_day: float
    phase: str
    cause: str  # explanation of what ended the mission


def final_report(
    analysis: MissionAnalysis,
    outcomes: Sequence[ScienceOutcome],
    *,
    experimental: bool,
    ratio: float,
    science: ScienceAnalysis | None = None,
    returned_scale: float = 1.0,
    incidents: Sequence[Incident] = (),
    termination: TerminationInfo | None = None,
    nominal: bool = True,
) -> FinalReport:
    sci = science if science is not None else analysis.science
    issues = [c for c in analysis.constraints if c.status in ("fail", "warning")]
    if termination is not None:
        outcome = "terminated"
    elif (
        outcomes
        and analysis.feasibility != "infeasible"
        and all(o.status == "achieved" for o in outcomes)
    ):
        outcome = "success"
    elif not outcomes or all(o.status == "missed" for o in outcomes):
        outcome = "failure"
    else:
        outcome = "partial"
    achieved = sum(1 for o in outcomes if o.status == "achieved")
    kind = "Experimental" if experimental else ("Nominal" if not incidents else "Flown")
    summary = (
        f"{kind} run of a {analysis.feasibility} "
        f"design: {achieved}/{len(outcomes)} objectives achieved; "
        f"{_clamp01(sci.returned_fraction * returned_scale):.0%} of the science returned, "
        f"{sci.collected_fraction:.0%} collected; score "
        f"{analysis.score.total:.1f}."
    )
    if incidents:
        summary += f" {len(incidents)} anomaly/scenario event(s) occurred."
    root_causes = [c.explanation for c in issues]
    root_causes += [f"{i.title} (day {i.mission_day:g}): {i.why}." for i in incidents]
    if termination is not None:
        summary = (
            f"Mission terminated on day {termination.mission_day:g} during "
            f"{termination.phase}: {termination.cause}. Postmortem: {summary}"
        )
        root_causes.insert(0, f"Termination: {termination.cause}.")
    counterfactuals = tuple(
        dict.fromkeys(
            [f"{a.label}: {a.expected_effect}" for c in issues for a in c.suggested_actions]
            + [i.counterfactual for i in incidents]
        )
    )
    middle = (NOMINAL_LIMITATION,) if nominal else EFFECT_LIMITATIONS
    limitations: tuple[str, ...] = (*BASE_LIMITATIONS, *middle, CATALOG_LIMITATION)
    if ratio <= 0.0:
        limitations = (*limitations, NO_RETURN_LIMITATION)
    if termination is not None:
        limitations = (*limitations, TERMINATION_LIMITATION.format(day=termination.mission_day))
    risks = [f"{c.id} ({c.status}): {c.label}" for c in issues]
    risks += [
        f"{i.declared_id} ({i.event_type}, day {i.mission_day:g}): {i.title}"
        + (f"; choice: {i.choice_label}" if i.choice_label else "")
        for i in incidents
    ]
    return FinalReport.model_validate(
        {
            "outcome": outcome,
            "summary": summary,
            "score": analysis.score,
            "realized_risks": tuple(risks),
            "root_causes": tuple(dict.fromkeys(root_causes)),
            "counterfactuals": counterfactuals,
            "limitations": limitations,
        }
    )


__all__ = [
    "ACHIEVED_RETURNED_FRACTION",
    "BASE_LIMITATIONS",
    "EFFECT_LIMITATIONS",
    "LIMITATIONS",
    "Incident",
    "TerminationInfo",
    "final_report",
    "return_ratio",
    "science_outcomes",
]
