"""Health monitor for a recorded run (Task 6.7). No HTTP types here.

The expected envelope is the NOMINAL MODEL: the same design, seed and engine flown with the
no-anomaly event set. Residuals are the run's telemetry minus that model at each checkpoint.
"""

from bisect import bisect_right
from dataclasses import dataclass
from datetime import datetime

from app.domain.health_monitor import detect_anomalies, trace_channel
from app.domain.health_monitor.detectors import DETECTORS
from app.schemas.health import (
    Anomaly,
    HealthChannelTrace,
    HealthFinding,
    HealthReport,
    HealthTracePoint,
)
from app.schemas.simulation import MissionEvent, MissionRun, SimulationInput, TelemetrySample
from app.services.mission_service import ValidationOutcome
from app.services.simulation_service import SimulationService

NOMINAL_EVENT_SET = "nominal-v1"
EXPLAIN_LOOKBACK_DAYS = 30.0

ASSUMPTIONS = [
    "Expected values come from the nominal model: the same design, seed and engine flown "
    "with the no-anomaly event set; telemetry is sampled at checkpoints, not continuously.",
    "Thresholds, persistence counts and lambda are gameplay-estimates, one detector per "
    "channel; this is a transparent EWMA rule, not a trained anomaly detector.",
    "A finding with no scenario event in the preceding 30 days is reported as a likely "
    "false positive.",
    "The nominal model is computed by the current engine and catalogue; for a run recorded "
    "under other versions, residuals include the version difference.",
]


@dataclass(frozen=True)
class HealthOutcome:
    report: HealthReport | None = None
    failure: ValidationOutcome | None = None


def expected_at(nominal: list[TelemetrySample], days: list[float]) -> list[float]:
    """Step interpolation: the nominal value at or before each day (first value before)."""
    nd = [s.mission_day for s in nominal]
    return [nominal[max(bisect_right(nd, d) - 1, 0)].value for d in days]


def _explain(anomaly: Anomaly, run: MissionRun) -> tuple[MissionEvent | None, str | None]:
    candidates = [
        e
        for e in run.events
        if e.type in ("anomaly", "decision")
        and anomaly.window_start - EXPLAIN_LOOKBACK_DAYS <= e.mission_day <= anomaly.window_end
    ]
    before = [e for e in candidates if e.mission_day <= anomaly.window_start]
    event: MissionEvent | None
    if before:  # the latest event that precedes the departure explains it best
        event = max(before, key=lambda e: (e.mission_day, e.sequence))
    else:  # otherwise the first event inside the alarm window
        event = min(candidates, key=lambda e: (e.mission_day, e.sequence), default=None)
    if event is None:
        return None, None
    rec = next((d for d in run.decisions if d.event_id == event.id), None)
    return event, (f"{rec.event_id} -> {rec.choice_id}" if rec else None)


class HealthMonitorService:
    def __init__(self, simulation: SimulationService) -> None:
        self._simulation = simulation

    def monitor(self, run: MissionRun, now: datetime) -> HealthOutcome:
        outcome = self._simulation.run_analysis(run, now)
        if outcome.analysis is None:
            return HealthOutcome(failure=outcome)
        sim_input = SimulationInput(
            mission_state=run.input_snapshot,
            analysis=outcome.analysis,
            # the nominal model is always built by the CURRENT engine and catalogue
            engine_version=self._simulation.engine_version,
            catalog_version=self._simulation.catalog.version,
            random_seed=run.seed,
            scenario_event_set_id=NOMINAL_EVENT_SET,
            experimental=run.experimental,
        )
        nominal = self._simulation.build_run(sim_input)
        channels: list[HealthChannelTrace] = []
        findings: list[HealthFinding] = []
        for config, category, subsystems in DETECTORS:
            samples = sorted(
                (s for s in run.telemetry if s.channel == config.channel),
                key=lambda s: s.mission_day,
            )
            base = sorted(
                (s for s in nominal.telemetry if s.channel == config.channel),
                key=lambda s: s.mission_day,
            )
            if not samples or not base:
                continue
            expected = expected_at(base, [s.mission_day for s in samples])
            points = trace_channel(samples, config, expected)
            channels.append(
                HealthChannelTrace(
                    config=config,
                    category=category,
                    points=[
                        HealthTracePoint(
                            mission_day=p.mission_day,
                            observed=p.observed,
                            expected=p.expected,
                            residual=p.residual,
                            ewma=p.ewma,
                            persistence=p.persistence,
                            state=p.state,
                        )
                        for p in points
                    ],
                )
            )
            for a in detect_anomalies(samples, config, expected, subsystems=subsystems):
                event, recovery = _explain(a, run)
                if event is None:
                    text = (
                        "No scenario event precedes this departure: treat it as a likely "
                        "false positive of a tight threshold before acting."
                    )
                else:
                    text = f"Explained by event {event.id} ({event.title})" + (
                        f"; recovery decision {recovery}." if recovery else "."
                    )
                findings.append(
                    HealthFinding(
                        anomaly=a,
                        related_event_id=event.id if event else None,
                        recovery_decision=recovery,
                        likely_false_positive=event is None,
                        explanation=text,
                    )
                )
        findings.sort(key=lambda f: (f.anomaly.window_start, f.anomaly.channel))
        return HealthOutcome(
            report=HealthReport(
                run_id=run.run_id,
                nominal_event_set_id=NOMINAL_EVENT_SET,
                channels=channels,
                findings=findings,
                assumptions=list(ASSUMPTIONS),
            )
        )
