"""Science belief orchestration (Task 6.4). Loads authored scenario models; no HTTP types."""

import json
from dataclasses import dataclass
from pathlib import Path

from app.domain.errors import DomainValidationError
from app.domain.science_belief import (
    ScienceModel,
    draw_outcome,
    initial_belief,
    rank_observations,
    update_belief,
)
from app.schemas.mission import MissionState
from app.schemas.science_belief import (
    BeliefState,
    ObservationLikelihood,
    ScienceHypothesis,
)

# <repo>/data/scenarios (services -> app -> backend -> repo).
DEFAULT_SCENARIOS_DIR = Path(__file__).resolve().parents[3] / "data" / "scenarios"
MAX_HISTORY = 50


def load_science_models(directory: Path = DEFAULT_SCENARIOS_DIR) -> dict[str, ScienceModel]:
    models: dict[str, ScienceModel] = {}
    for path in sorted(directory.glob("*.science.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        models[raw["scenarioId"]] = ScienceModel(
            scenario_id=raw["scenarioId"],
            version=raw["version"],
            hypotheses=tuple(ScienceHypothesis.model_validate(h) for h in raw["hypotheses"]),
            likelihoods=tuple(ObservationLikelihood.model_validate(t) for t in raw["likelihoods"]),
        )
    return models


@dataclass(frozen=True)
class ObservedOutcome:
    instrument_id: str
    outcome_id: str


@dataclass(frozen=True)
class NextObservation:
    instrument_id: str
    expected_information_gain_bits: float
    outcome_probabilities: dict[str, float]


@dataclass(frozen=True)
class BeliefResult:
    model: ScienceModel
    belief: BeliefState
    history: list[ObservedOutcome]
    next_observations: list[NextObservation]
    last_outcome: ObservedOutcome | None


class ScienceService:
    def __init__(self, models: dict[str, ScienceModel]) -> None:
        self._models = models

    def model_for(self, scenario_id: str) -> ScienceModel | None:
        return self._models.get(scenario_id)

    def belief(
        self,
        state: MissionState,
        history: list[ObservedOutcome],
        observe_with: str | None,
    ) -> BeliefResult:
        """Replay `history`, optionally simulate one more observation, rank what to do next.

        Raises LookupError when the scenario has no science model, DomainValidationError
        for unknown instruments/outcomes or an over-long history.
        """
        model = self._models.get(state.scenario_id)
        if model is None:
            raise LookupError(state.scenario_id)
        if len(history) + (1 if observe_with else 0) > MAX_HISTORY:
            raise DomainValidationError("HISTORY_TOO_LONG", "history", f"at most {MAX_HISTORY}")
        belief = initial_belief(model)
        steps = list(history)
        last: ObservedOutcome | None = None
        if observe_with is not None:
            selected = set(state.architecture.instrument_ids)
            if observe_with not in selected or not model.tables(observe_with):
                raise DomainValidationError(
                    "INSTRUMENT_NOT_AVAILABLE",
                    "observeWith",
                    "that instrument is not on this spacecraft or has no science model",
                )
            index = sum(h.instrument_id == observe_with for h in steps)
            last = ObservedOutcome(
                observe_with, draw_outcome(model, state.random_seed, observe_with, index)
            )
            steps.append(last)
        for i, step in enumerate(steps):
            belief = update_belief(
                belief,
                model.table(step.instrument_id, step.outcome_id),
                task_id=f"{step.instrument_id}#{i}",
            )
        ranked = rank_observations(belief, model, state.architecture.instrument_ids)
        return BeliefResult(
            model=model,
            belief=belief,
            history=steps,
            next_observations=[NextObservation(i, eig, p) for i, eig, p in ranked],
            last_outcome=last,
        )
