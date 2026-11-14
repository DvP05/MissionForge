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

Outcome rule: ``terminated`` only when the run ended early (Task 4.2); ``success`` when the
design is not infeasible and every objective is achieved; ``failure`` when no objective
returned anything (or there are no objectives); otherwise ``partial``.
"""

from collections.abc import Sequence

from app.domain.analysis.context import AnalysisContext
from app.domain.simulation.phases import PHASE_ASSUMPTIONS
from app.domain.simulation.telemetry import TELEMETRY_ASSUMPTIONS
from app.schemas.analysis import MissionAnalysis
from app.schemas.mission import MissionState
from app.schemas.simulation import FinalReport, ScienceOutcome

ACHIEVED_RETURNED_FRACTION = 0.8  # gameplay-estimate threshold

LIMITATIONS: tuple[str, ...] = (
    "deterministic event simulation; not orbital propagation",
    *PHASE_ASSUMPTIONS,
    *TELEMETRY_ASSUMPTIONS,
    "Nominal run: no anomalies or decisions are injected.",
    "All catalogue values are illustrative gameplay-estimate archetypes.",
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
    state: MissionState, analysis: MissionAnalysis, ratio: float
) -> tuple[ScienceOutcome, ...]:
    cov = analysis.science.weighted_objective_coverage
    out: list[ScienceOutcome] = []
    for o in state.science_objectives:
        returned = _clamp01(cov.get(o.id, 0.0))
        collected = (
            _clamp01(returned / ratio) if ratio > 0.0 else analysis.science.collected_fraction
        )
        collected = max(collected, returned)
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


def final_report(
    analysis: MissionAnalysis,
    outcomes: Sequence[ScienceOutcome],
    *,
    experimental: bool,
    ratio: float,
) -> FinalReport:
    issues = [c for c in analysis.constraints if c.status in ("fail", "warning")]
    if (
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
    summary = (
        f"{'Experimental' if experimental else 'Nominal'} run of a {analysis.feasibility} "
        f"design: {achieved}/{len(outcomes)} objectives achieved; "
        f"{analysis.science.returned_fraction:.0%} of the science returned, "
        f"{analysis.science.collected_fraction:.0%} collected; score "
        f"{analysis.score.total:.1f}."
    )
    counterfactuals = tuple(
        dict.fromkeys(
            f"{a.label}: {a.expected_effect}" for c in issues for a in c.suggested_actions
        )
    )
    limitations = LIMITATIONS if ratio > 0.0 else (*LIMITATIONS, NO_RETURN_LIMITATION)
    return FinalReport.model_validate(
        {
            "outcome": outcome,
            "summary": summary,
            "score": analysis.score,
            "realized_risks": tuple(f"{c.id} ({c.status}): {c.label}" for c in issues),
            "root_causes": tuple(c.explanation for c in issues),
            "counterfactuals": counterfactuals,
            "limitations": limitations,
        }
    )


__all__ = [
    "ACHIEVED_RETURNED_FRACTION",
    "LIMITATIONS",
    "final_report",
    "return_ratio",
    "science_outcomes",
]
