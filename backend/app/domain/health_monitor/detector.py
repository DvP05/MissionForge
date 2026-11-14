"""Deterministic EWMA residual detector for gameplay telemetry."""

from collections.abc import Sequence

from app.schemas.health import Anomaly, DetectorConfig
from app.schemas.simulation import TelemetrySample


def detect_anomalies(
    samples: Sequence[TelemetrySample],
    config: DetectorConfig,
) -> list[Anomaly]:
    """Detect persistent residuals and hard-limit crossings without changing telemetry."""
    matching = [
        sample
        for sample in samples
        if sample.channel == config.channel and sample.unit == config.unit
    ]
    matching.sort(key=lambda sample: sample.mission_day)
    ewma = 0.0
    streak = 0
    candidates: list[tuple[TelemetrySample, float, float]] = []
    anomalies: list[Anomaly] = []

    for sample in matching:
        residual = sample.value - config.expected
        ewma = config.lam * residual + (1 - config.lam) * ewma
        hard_crossed = config.hard_limit is not None and abs(sample.value) >= abs(config.hard_limit)
        if hard_crossed:
            anomalies.append(
                Anomaly(
                    channel=config.channel,
                    unit=config.unit,
                    observed=sample.value,
                    baseline=config.expected,
                    threshold=config.hard_limit,
                    window_start=sample.mission_day,
                    window_end=sample.mission_day,
                    severity="critical",
                    subsystems=[],
                    explanation=(
                        f"{config.channel} observed {sample.value:g} {config.unit}; "
                        f"hard safety limit {config.hard_limit:g} {config.unit} was crossed."
                    ),
                )
            )
            streak = 0
            candidates.clear()
            continue

        magnitude = abs(ewma)
        if magnitude >= config.warn:
            streak += 1
            candidates.append((sample, ewma, magnitude))
        else:
            streak = 0
            candidates.clear()

        if streak >= config.persistence_k:
            start = candidates[0][0]
            severity = "critical" if magnitude >= config.crit else "warning"
            anomalies.append(
                Anomaly(
                    channel=config.channel,
                    unit=config.unit,
                    observed=sample.value,
                    baseline=config.expected + ewma,
                    threshold=config.crit if severity == "critical" else config.warn,
                    window_start=start.mission_day,
                    window_end=sample.mission_day,
                    severity=severity,
                    subsystems=[],
                    explanation=(
                        f"{config.channel} residual persisted for {streak} samples: "
                        f"observed {sample.value:g} {config.unit}, EWMA residual {ewma:g}, "
                        f"baseline {config.expected:g} {config.unit}; "
                        f"{severity} threshold "
                        f"{config.crit if severity == 'critical' else config.warn:g}."
                    ),
                )
            )
            streak = 0
            candidates.clear()

    return anomalies
