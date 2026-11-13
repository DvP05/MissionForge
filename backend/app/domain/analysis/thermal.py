"""Qualitative thermal check (architecture §7.6). No thermal balance is computed.

Never returns ``"pass"`` and never emits a temperature: without a validated thermal
model the strongest honest outcomes are a risk flag ("warning") or "not-modelled".
"""

from typing import Literal

from app.domain.catalog.resolver import ResolvedArchitecture
from app.domain.errors import DomainValidationError
from app.schemas.analysis import ConstraintResult, SuggestedAction

ThermalExposure = Literal["benign", "cold", "hot", "extreme"]

THERMAL_ASSUMPTIONS: tuple[str, ...] = (
    "Thermal is a qualitative capability check against the scenario exposure class; no "
    "thermal balance or temperature is computed.",
)

_REQUIRED: dict[str, tuple[str, ...]] = {
    "benign": (),
    "cold": ("heaters",),
    "hot": ("radiator",),
    "extreme": ("heaters", "radiator"),
}
# ConstraintResult severity scale 0-3: 1 = single missing capability (minor risk flag),
# 2 = both heaters and radiator missing (significant risk flag). 3 (critical) is reserved
# for modelled failures, which this qualitative check never produces.
_SEVERITY_ONE_MISSING = 1
_SEVERITY_BOTH_MISSING = 2
_LABEL = "Thermal control"
_NOT_MODELLED = "qualitative check only — no thermal balance computed"


def thermal_check(
    resolved: ResolvedArchitecture, exposure: ThermalExposure | None
) -> ConstraintResult:
    if exposure is None:
        return ConstraintResult(
            id="thermal",
            label=_LABEL,
            status="not-modelled",
            severity=0,
            explanation="thermal not modelled: no exposure class",
        )
    if exposure not in _REQUIRED:
        raise DomainValidationError(
            "UNKNOWN_EXPOSURE", "exposure", f"unknown thermal exposure class {exposure!r}"
        )
    have = set(resolved.thermal.capabilities)
    missing = [cap for cap in _REQUIRED[exposure] if cap not in have]
    if not missing:
        return ConstraintResult(
            id="thermal",
            label=_LABEL,
            status="not-modelled",
            severity=0,
            explanation=_NOT_MODELLED,
        )
    return ConstraintResult(
        id="thermal",
        label=_LABEL,
        status="warning",
        severity=_SEVERITY_BOTH_MISSING if len(missing) > 1 else _SEVERITY_ONE_MISSING,
        explanation=(
            f"Risk flag (qualitative, not a thermal analysis): '{exposure}' exposure but the "
            f"selected thermal system lacks capability: {', '.join(missing)}."
        ),
        impacted_subsystems=["thermal"],
        suggested_actions=[
            SuggestedAction(
                action_id=f"add-thermal-{cap}",
                label=f"Choose a thermal system with {cap}",
                expected_effect=f"Covers the {exposure} exposure class qualitatively.",
            )
            for cap in missing
        ],
    )
