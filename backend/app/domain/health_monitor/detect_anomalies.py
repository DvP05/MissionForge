"""Transparent EWMA-residual health monitor (architecture 19.7, Task 6.7).

Residual r_t = observed - expected, where ``expected`` is the nominal-model value at the
same checkpoint (or ``DetectorConfig.expected`` when no series is given). Rules:

* warning: |EWMA| > ``warn`` for ``persistence_k`` consecutive samples;
* critical: |EWMA| > ``crit`` or the hard safety limit is crossed (a hard limit below the
  expected value is a lower limit, above it an upper limit);
* hysteresis: an alarm clears only once |EWMA| drops below half the warning threshold.

One ``Anomaly`` per alarm episode. Deterministic and pure; no learning, no randomness.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.health_monitor.ewma import ewma
from app.schemas.health import Anomaly, DetectorConfig
from app.schemas.simulation import TelemetrySample

CLEAR_FRACTION = 0.5  # hysteresis: clear below warn x this


@dataclass(frozen=True)
class TracePoint:
    mission_day: float
    observed: float
    expected: float
    residual: float
    ewma: float
    persistence: int  # consecutive samples with |EWMA| > warn
    state: str  # "nominal" | "warning" | "critical"


def _hard_crossed(value: float, config: DetectorConfig, expected: float) -> bool:
    h = config.hard_limit
    if h is None:
        return False
    return value < h if h < expected else value > h


def trace_channel(
    samples: Sequence[TelemetrySample],
    config: DetectorConfig,
    expected: Sequence[float] | None = None,
) -> list[TracePoint]:
    exp = list(expected) if expected is not None else [config.expected] * len(samples)
    residuals = [s.value - m for s, m in zip(samples, exp, strict=True)]
    smoothed = ewma(residuals, config.lam)
    points: list[TracePoint] = []
    run = 0
    active = "nominal"
    for s, m, r, e in zip(samples, exp, residuals, smoothed, strict=True):
        run = run + 1 if abs(e) > config.warn else 0
        if abs(e) > config.crit or _hard_crossed(s.value, config, m):
            active = "critical"
        elif run >= config.persistence_k and active != "critical":
            active = "warning"
        elif active != "nominal" and abs(e) < config.warn * CLEAR_FRACTION:
            active = "nominal"
        points.append(TracePoint(s.mission_day, s.value, m, r, e, run, active))
    return points


def detect_anomalies(
    samples: Sequence[TelemetrySample],
    config: DetectorConfig,
    expected: Sequence[float] | None = None,
    *,
    subsystems: Sequence[str] = (),
) -> list[Anomaly]:
    """Alarm episodes of one channel; samples must be that channel, in time order."""
    points = trace_channel(samples, config, expected)
    out: list[Anomaly] = []
    episode: list[TracePoint] = []

    def close() -> None:
        if not episode:
            return
        critical = any(p.state == "critical" for p in episode)
        peak = max(episode, key=lambda p: abs(p.ewma))
        threshold = config.crit if critical else config.warn
        hard = config.hard_limit is not None and any(
            _hard_crossed(p.observed, config, p.expected) for p in episode
        )
        rule = (
            f"hard safety limit {config.hard_limit:g} {config.unit} crossed"
            if hard
            else f"|EWMA residual| {abs(peak.ewma):.3g} > {threshold:g} {config.unit}"
            + ("" if critical else f" for {config.persistence_k}+ consecutive samples")
        )
        out.append(
            Anomaly(
                channel=config.channel,
                unit=config.unit,
                observed=peak.observed,
                baseline=peak.expected,
                threshold=threshold,
                window_start=episode[0].mission_day,
                window_end=episode[-1].mission_day,
                severity="critical" if critical else "warning",
                subsystems=list(subsystems),
                explanation=(
                    f"{config.channel} departs from the nominal model between day "
                    f"{episode[0].mission_day:g} and {episode[-1].mission_day:g}: {rule} "
                    f"(lambda {config.lam:g})."
                ),
            )
        )
        episode.clear()

    for p in points:
        if p.state == "nominal":
            close()
        else:
            episode.append(p)
    close()
    return out
