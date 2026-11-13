import pytest

from app.domain.analysis.thermal import thermal_check
from tests.unit.analysis._arch import arch, comp


def test_never_pass_without_inputs() -> None:
    r = thermal_check(arch(), None)
    assert r.id == "thermal" and r.status == "not-modelled"
    assert r.explanation == "thermal not modelled: no exposure class"
    assert r.actual is None


@pytest.mark.parametrize(
    ("exposure", "caps", "missing"),
    [
        ("cold", [], "heaters"),
        ("hot", [], "radiator"),
        ("extreme", ["heaters"], "radiator"),
        ("extreme", ["radiator"], "heaters"),
        ("extreme", [], "heaters"),
    ],
)
def test_warning_when_capability_missing(exposure: str, caps: list[str], missing: str) -> None:
    a = arch(thermal=comp("t", "thermal", 1.0, caps=caps))
    r = thermal_check(a, exposure)  # type: ignore[arg-type]
    assert r.status == "warning"
    assert 1 <= r.severity <= 2
    assert r.impacted_subsystems == ["thermal"]
    assert any(missing in s.label for s in r.suggested_actions)
    assert r.actual is None


@pytest.mark.parametrize(
    ("exposure", "caps"),
    [
        ("benign", []),
        ("cold", ["heaters"]),
        ("hot", ["radiator"]),
        ("extreme", ["heaters", "radiator"]),
    ],
)
def test_otherwise_not_modelled(exposure: str, caps: list[str]) -> None:
    a = arch(thermal=comp("t", "thermal", 1.0, caps=caps))
    r = thermal_check(a, exposure)  # type: ignore[arg-type]
    assert r.status == "not-modelled"
    assert r.explanation == "qualitative check only — no thermal balance computed"
