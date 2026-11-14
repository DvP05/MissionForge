"""Mission simulation orchestration + the in-memory run store (Task 4.3, ruling R32).

Runs are immutable. A player decision never edits a run: it re-runs the stored input with the
decision added and stores the result as a NEW run. The store is a bounded LRU held in process
memory (lost on restart or eviction); the client keeps its own copy (persistence, Task 4.5).
"""

import json
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Generic, TypeVar

from app.domain.catalog.loader import Catalog
from app.domain.errors import DomainValidationError
from app.domain.simulation.anomalies import ScenarioEventSet, default_event_set_id
from app.domain.simulation.runner import run_mission
from app.schemas.mission import SCHEMA_VERSION, MissionState
from app.schemas.simulation import MissionRun, SimulationInput
from app.services.mission_service import MissionService, ValidationOutcome
from app.services.template_service import TemplateService

RUN_STORE_CAPACITY = 50


def _normalise_numbers(value: Any) -> Any:
    """Integral floats become ints so 275 and 275.0 compare equal (bools stay bools)."""
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, dict):
        return {k: _normalise_numbers(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalise_numbers(v) for v in value]
    return value


def canonical_run_json(run: MissionRun) -> str:
    """Serialised run for identity checks.

    Identical except that a number is compared by value: a run that went through JavaScript
    (browser storage, export file) comes back with ``275`` where Python wrote ``275.0``, and
    that is the same recorded value, not a different run.
    """
    data = json.loads(run.model_dump_json(by_alias=True))
    return json.dumps(_normalise_numbers(data), sort_keys=True, separators=(",", ":"))


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
class VersionMismatch:
    """One way an imported run differs from what this server would use to replay it."""

    field: str
    recorded: str
    current: str


@dataclass(frozen=True)
class ReplayOutcome:
    """Honest replay result: `identical` only after comparing the re-run with the recorded run."""

    status: str  # "identical-replay" | "version-mismatch" | "diverged"
    mismatches: tuple[VersionMismatch, ...] = ()
    run: MissionRun | None = None

    @property
    def identical(self) -> bool:
        return self.status == "identical-replay"


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

    @property
    def catalog(self) -> Catalog:
        return self._catalog

    def _build(
        self,
        sim_input: SimulationInput,
        decisions: dict[str, str],
        app_version: str | None = None,
    ) -> StoredRun:
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
            app_version=app_version or self._app_version,
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

    # ---- Replay (Task 4.5, architecture 16, module_breakdown 12.6) -------------------------

    def version_mismatches(self, run: MissionRun) -> list[VersionMismatch]:
        """Compare the run manifest with this server. Never claims anything about the output."""
        man = run.manifest
        template = self._templates.get(run.input_snapshot.scenario_id)
        pairs = [
            ("schemaVersion", man.schema_version, SCHEMA_VERSION),
            ("engineVersion", man.engine_version, self._engine_version),
            ("catalogVersion", man.catalog_version, self._catalog.version),
            (
                "scenarioVersion",
                man.scenario_version,
                template.scenario_version if template is not None else "unavailable",
            ),
        ]
        out = [VersionMismatch(f, rec, cur) for f, rec, cur in pairs if rec != cur]
        event_set = self._event_sets.get(man.event_set_id)
        if event_set is None:
            out.append(VersionMismatch("eventSet", man.event_set_id, "unavailable"))
        elif (
            event_set.scenario_ids and run.input_snapshot.scenario_id not in event_set.scenario_ids
        ):
            out.append(VersionMismatch("eventSet", man.event_set_id, "does not apply"))
        return out

    def run_analysis(self, run: MissionRun, now: datetime) -> ValidationOutcome:
        """Analysis of the run's snapshot with the CURRENT engine (derived, may differ)."""
        return self._missions.validate(run.input_snapshot, now)

    def replay(self, run: MissionRun, now: datetime) -> ReplayOutcome:
        """Re-run from snapshot, seed, event set and recorded player decisions; compare the result.

        Not run at all when versions differ: a different engine can never be an identical replay.
        """
        mismatches = self.version_mismatches(run)
        if mismatches:
            return ReplayOutcome("version-mismatch", tuple(mismatches))
        outcome = self.run_analysis(run, now)
        if outcome.analysis is None:
            return ReplayOutcome(
                "version-mismatch",
                (VersionMismatch("design", "valid", "fails validation in this catalogue"),),
            )
        sim_input = SimulationInput(
            mission_state=run.input_snapshot,
            analysis=outcome.analysis,
            engine_version=self._engine_version,
            catalog_version=self._catalog.version,
            random_seed=run.seed,
            scenario_event_set_id=run.scenario_event_set_id,
            experimental=run.experimental,
        )
        decisions = {d.event_id: d.choice_id for d in run.decisions if d.decision_maker == "player"}
        try:
            # app_version is a metadata stamp only; replay under the recorded one so a pure
            # app release does not make an otherwise identical run look different.
            rebuilt = self._build(sim_input, decisions, app_version=run.manifest.app_version).run
        except DomainValidationError as exc:
            # Versions matched, so a rejected re-run means the recorded data is inconsistent.
            return ReplayOutcome("diverged", (VersionMismatch("replay", exc.code, "rejected"),))
        if canonical_run_json(rebuilt) == canonical_run_json(run):
            return ReplayOutcome("identical-replay", (), rebuilt)
        return ReplayOutcome(
            "diverged", (VersionMismatch("output", "recorded run", "re-run differs"),), rebuilt
        )
