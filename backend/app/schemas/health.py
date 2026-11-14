"""Predictive health-monitor contracts (architecture 19.7). Owner: simulation lead.

Transparent EWMA-residual monitor: `EWMA_t = lam * r_t + (1 - lam) * EWMA_{t-1}` with
`r_t = x_t - expected`; warning when |EWMA| > `warn` for `persistence_k` consecutive
samples, critical when |EWMA| > `crit` or the hard safety limit is crossed. Window times
are mission days (same clock as TelemetrySample.mission_day).
"""

from typing import Literal, Self

from pydantic import Field, StrictInt, model_validator

from app.schemas.api import ContractModel
from app.schemas.units import FiniteFloat, NonNegativeFloat, Unit


class DetectorConfig(ContractModel):
    channel: str
    unit: Unit
    expected: FiniteFloat  # expected (nominal) value m_t of the channel
    warn: NonNegativeFloat  # |EWMA residual| warning threshold
    crit: NonNegativeFloat  # |EWMA residual| critical threshold
    persistence_k: StrictInt = Field(ge=1)
    hard_limit: FiniteFloat | None = None
    lam: FiniteFloat = Field(gt=0, le=1)
    rationale: str

    @model_validator(mode="after")
    def _thresholds_ordered(self) -> Self:
        if self.warn > self.crit:
            raise ValueError("warn must be <= crit")
        return self


class Anomaly(ContractModel):
    channel: str
    unit: Unit
    observed: FiniteFloat
    baseline: FiniteFloat
    threshold: FiniteFloat
    window_start: NonNegativeFloat
    window_end: NonNegativeFloat
    severity: Literal["warning", "critical"]
    subsystems: list[str]
    explanation: str

    @model_validator(mode="after")
    def _window_ordered(self) -> Self:
        if self.window_end < self.window_start:
            raise ValueError("window_end must be >= window_start")
        return self


class HealthTracePoint(ContractModel):
    mission_day: NonNegativeFloat
    observed: FiniteFloat
    expected: FiniteFloat  # nominal-model value at this checkpoint
    residual: FiniteFloat
    ewma: FiniteFloat
    persistence: StrictInt = Field(ge=0)
    state: Literal["nominal", "warning", "critical"]


class HealthChannelTrace(ContractModel):
    config: DetectorConfig
    category: Literal["power-thermal", "attitude-pointing", "comms-data", "propulsion"]
    points: list[HealthTracePoint]


class HealthFinding(ContractModel):
    anomaly: Anomaly
    related_event_id: str | None = None  # the scenario event that explains it, if any
    recovery_decision: str | None = None  # "<event id> -> <choice id>" when one was made
    likely_false_positive: bool = False
    explanation: str


class HealthReport(ContractModel):
    """Health-monitor result for one run (Task 6.7); derived, recomputed on request."""

    run_id: str
    nominal_event_set_id: str
    channels: list[HealthChannelTrace]
    findings: list[HealthFinding]
    assumptions: list[str]
