"""Mission simulation orchestration + the in-memory run store (Task 4.3, ruling R32).

Runs are immutable. A player decision never edits a run: it re-runs the stored input with the
decision added and stores the result as a NEW run. The store is a bounded LRU held in process
memory (lost on restart or eviction); the client keeps its own copy (persistence, Task 4.5).
"""

import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Generic, TypeVar

from app.domain.catalog.loader import Catalog
from app.domain.simulation.anomalies import ScenarioEventSet, default_event_set_id
from app.domain.simulation.runner import run_mission
from app.schemas.mission import MissionState
from app.schemas.simulation import MissionRun, SimulationInput
from app.services.mission_service import MissionService, ValidationOutcome
from app.services.template_service import TemplateService

RUN_STORE_CAPACITY = 50

V = TypeVar("V")


class RunStore(Generic[V]):  # noqa: UP046 - TypeVar keeps the class usable as RunStore[int]
    """Thread-safe bounded LRU. get() and put() both mark a key most recently used."""

    def __init__(self, capacity: int = RUN_STORE_CAPACITY) -> None:
        if capacity < 1:
            raise ValueError("capacity must be >= 1")
        self._capacity = capacity
        self._items: OrderedDict[str, V] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> V | None:
        with self._lock:
            if key not in self._items:
                return None
            self._items.move_to_end(key)
            return self._items[key]

    def put(self, key: str, value: V) -> None:
        with self._lock:
            self._items[key] = value
            self._items.move_to_end(key)
            while len(self._items) > self._capacity:
                self._items.popitem(last=False)

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)


@dataclass(frozen=True)
class StoredRun:
    """The run plus the exact input needed to re-run it with another decision."""

    run: MissionRun
    sim_input: SimulationInput
    decisions: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SimulateOutcome:
    """Either a stored run or the failed validation outcome (R22)."""

    stored: StoredRun | None = None
    failure: ValidationOutcome | None = None


class RunNotFoundError(LookupError):
    """Unknown run id, or the run was evicted from the bounded store."""


class DecisionAlreadyMadeError(ValueError):
    """The player already decided this event in the source run."""


class SimulationService:
    def __init__(
        self,
        missions: MissionService,
        catalog: Catalog,
        templates: TemplateService,
        event_sets: dict[str, ScenarioEventSet],
        *,
        engine_version: str,
        app_version: str,
        store: RunStore[StoredRun] | None = None,
    ) -> None:
        self._missions = missions
        self._catalog = catalog
        self._templates = templates
        self._event_sets = event_sets
        self._engine_version = engine_version
        self._app_version = app_version
        self._store: RunStore[StoredRun] = store if store is not None else RunStore()

    def _build(self, sim_input: SimulationInput, decisions: dict[str, str]) -> StoredRun:
        state = sim_input.mission_state
        template = self._templates.get(state.scenario_id)
        scenario = self._templates.scenario_inputs(state.scenario_id)
        if template is None or scenario is None:  # unreachable for the Literal scenario ids
            raise LookupError(f"no template for scenario {state.scenario_id!r}")
        run = run_mission(
            sim_input,
            self._catalog,
            scenario=scenario,
            event_sets=self._event_sets,
            scenario_version=template.scenario_version,
            app_version=self._app_version,
            decisions=decisions,
        )
        return StoredRun(run=run, sim_input=sim_input, decisions=dict(decisions))

    def _run(self, sim_input: SimulationInput, decisions: dict[str, str]) -> StoredRun:
        stored = self._build(sim_input, decisions)
        self._store.put(stored.run.run_id, stored)
        return stored

    def simulate(
        self,
        state: MissionState,
        *,
        seed: int,
        event_set_id: str | None,
        experimental: bool,
        decisions: dict[str, str],
        now: datetime,
    ) -> SimulateOutcome:
        """Validate (R22), analyse server-side, run. Domain errors propagate to the route."""
        outcome = self._missions.validate(state, now)
        if outcome.analysis is None:
            return SimulateOutcome(failure=outcome)
        sim_input = SimulationInput(
            mission_state=state,
            analysis=outcome.analysis,
            engine_version=self._engine_version,
            catalog_version=self._catalog.version,
            random_seed=seed,
            scenario_event_set_id=event_set_id
            or default_event_set_id(state.scenario_id, self._event_sets),
            experimental=experimental,
        )
        return SimulateOutcome(stored=self._run(sim_input, decisions))

    def get(self, run_id: str) -> StoredRun:
        stored = self._store.get(run_id)
        if stored is None:
            raise RunNotFoundError(run_id)
        return stored

    def decide(self, run_id: str, event_id: str, choice_id: str) -> StoredRun:
        """Branch: re-run the source input with the decision added; the source is untouched."""
        source = self.get(run_id)
        if any(
            d.event_id == event_id and d.decision_maker == "player" for d in source.run.decisions
        ):
            raise DecisionAlreadyMadeError(event_id)
        # The new choice may end the mission earlier and cancel later carried-over decisions.
        # Probe with the new decision alone (strict: it raises if the new decision is invalid),
        # then keep only the earlier player choices whose events still happen on this branch.
        probe = self._build(source.sim_input, {event_id: choice_id})
        occurring = {d.event_id for d in probe.run.decisions}
        kept = {k: v for k, v in source.decisions.items() if k in occurring and k != event_id}
        return self._run(source.sim_input, {**kept, event_id: choice_id})
