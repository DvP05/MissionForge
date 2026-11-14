from app.domain.health_monitor.detector import detect_anomalies
from app.schemas.health import DetectorConfig
from app.schemas.simulation import TelemetrySample


def _sample(day: float, value: float) -> TelemetrySample:
    return TelemetrySample(
        channel="pointing_error_deg",
        unit="deg",
        mission_day=day,
        value=value,
        fidelity="gameplay-estimate",
        phase="cruise",
    )


def _config(**updates: object) -> DetectorConfig:
    return DetectorConfig(
        channel="pointing_error_deg",
        unit="deg",
        expected=0.0,
        warn=0.5,
        crit=1.5,
        persistence_k=2,
        hard_limit=3.0,
        lam=1.0,
        rationale="test",
        **updates,
    )


def test_single_noncritical_spike_is_ignored() -> None:
    assert detect_anomalies([_sample(1, 0.8), _sample(2, 0.0)], _config()) == []


def test_persistent_deviation_is_reported() -> None:
    anomalies = detect_anomalies([_sample(1, 0.8), _sample(2, 0.9)], _config())
    assert len(anomalies) == 1
    assert anomalies[0].severity == "warning"
    assert anomalies[0].window_start == 1


def test_hard_limit_is_critical_immediately() -> None:
    anomalies = detect_anomalies([_sample(1, 3.2)], _config())
    assert len(anomalies) == 1
    assert anomalies[0].severity == "critical"
