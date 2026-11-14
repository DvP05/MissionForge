"""EWMA-residual health monitor rules (Task 6.7, architecture 19.7, AC-21)."""

import pytest

from app.domain.errors import DomainValidationError
from app.domain.health_monitor import detect_anomalies, ewma, trace_channel
from app.schemas.health import DetectorConfig
from app.schemas.simulation import TelemetrySample

CFG = DetectorConfig(
    channel="battery_soc", unit="fraction", expected=0.8, warn=0.05, crit=0.15,
    persistence_k=3, hard_limit=0.2, lam=0.5, rationale="test",
)  # fmt: skip


def _samples(values: list[float]) -> list[TelemetrySample]:
    return [
        TelemetrySample(channel="battery_soc", unit="fraction", mission_day=float(i),
                        value=v, fidelity="derived", phase="cruise")
        for i, v in enumerate(values)
    ]  # fmt: skip


def test_ewma_known_values_and_lambda_guard() -> None:
    assert ewma([1.0, 1.0, 1.0], 0.5) == [0.5, 0.75, 0.875]
    assert ewma([2.0, 0.0], 1.0) == [2.0, 0.0]
    with pytest.raises(DomainValidationError):
        ewma([1.0], 0.0)


def test_single_spike_below_hard_limit_is_not_critical() -> None:
    found = detect_anomalies(_samples([0.8, 0.8, 0.72, 0.8, 0.8, 0.8]), CFG)
    assert not [a for a in found if a.severity == "critical"]
    assert found == []  # one spike never persists for k samples


def test_k_consecutive_exceedances_raise_a_warning() -> None:
    found = detect_anomalies(_samples([0.8, 0.72, 0.72, 0.72, 0.72, 0.72]), CFG)
    assert [a.severity for a in found] == ["warning"]
    assert found[0].threshold == CFG.warn and "consecutive" in found[0].explanation


def test_crit_or_hard_limit_is_critical() -> None:
    deep = detect_anomalies(_samples([0.8, 0.5, 0.5, 0.5]), CFG)
    assert deep and deep[0].severity == "critical"
    hard = detect_anomalies(_samples([0.8, 0.8, 0.19, 0.8, 0.8, 0.8, 0.8]), CFG)
    assert hard and hard[0].severity == "critical" and "hard safety limit" in hard[0].explanation


def test_hysteresis_clears_only_below_the_lower_threshold() -> None:
    values = [0.8, 0.72, 0.72, 0.72, 0.77, 0.77, 0.8, 0.8, 0.8, 0.8]
    states = [p.state for p in trace_channel(_samples(values), CFG)]
    first_warn = states.index("warning")
    # |EWMA| between warn/2 and warn keeps the alarm on; it clears only later
    assert states[first_warn + 1] == "warning"
    assert states[-1] == "nominal"
    assert len(detect_anomalies(_samples(values), CFG)) == 1


def test_persistent_drift_detected_and_noise_ignored() -> None:
    drift = [0.8 - 0.012 * i for i in range(15)]
    assert detect_anomalies(_samples(drift), CFG)
    noise = [0.8 + (0.01 if i % 2 else -0.01) for i in range(30)]
    assert detect_anomalies(_samples(noise), CFG) == []


def test_expected_series_overrides_the_constant_and_is_deterministic() -> None:
    values = [0.7, 0.6, 0.5, 0.4]
    expected = [0.7, 0.6, 0.5, 0.4]  # the nominal model predicts the decline
    assert detect_anomalies(_samples(values), CFG, expected) == []
    a = detect_anomalies(_samples([0.8, 0.6, 0.6, 0.6]), CFG, subsystems=["power"])
    assert a == detect_anomalies(_samples([0.8, 0.6, 0.6, 0.6]), CFG, subsystems=["power"])
    assert a[0].subsystems == ["power"]
