"""Scenario template contract (data/missions/<scenario-id>.json).

A template is a curated starting point: narrative, top constraints, fidelity notes and a
MissionState without the per-instance fields (id, timestamps, seed), which are supplied by
`default_mission_state`.
"""

from typing import Literal

from pydantic import Field, StrictInt

from app.schemas._frozen import FrozenContract
from app.schemas.mission import (
    MissionConstraints,
    OperationsPlan,
    ScienceObjective,
    SpacecraftArchitecture,
)
from app.schemas.trajectory import Destination, TrajectorySelection
from app.schemas.units import FiniteFloat


class TemplateMissionState(FrozenContract):
    """MissionState minus missionId / createdAt / updatedAt / randomSeed."""

    schema_version: Literal["1.0"] = "1.0"
    title: str
    scenario_id: Literal["neo-rendezvous", "lunar-polar-scout", "earth-observation"]
    design_revision: StrictInt = Field(default=0, ge=0)
    science_objectives: tuple[ScienceObjective, ...]
    destination: Destination
    trajectory: TrajectorySelection
    architecture: SpacecraftArchitecture
    operations: OperationsPlan
    constraints: MissionConstraints


class ScenarioTemplate(FrozenContract):
    scenario_id: Literal["neo-rendezvous", "lunar-polar-scout", "earth-observation"]
    scenario_version: str
    title: str
    narrative: str
    top_constraints: tuple[str, ...] = Field(min_length=3, max_length=3)
    fidelity_notes: tuple[str, ...]
    reference_earth_range_m: FiniteFloat = Field(gt=0)
    optional_objectives: tuple[ScienceObjective, ...] = Field(default_factory=tuple)
    mission_state: TemplateMissionState
