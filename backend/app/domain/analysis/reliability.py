"""Reliability, risk index and FMEA helpers (architecture §7.9). Pure, deterministic.

R_i = prod over a component's failure modes of (1 - base_probability); R_system = prod R_i.
risk_index = sum(base_probability x severity) / (SEVERITY_MAX x number of modes), in 0..1.
RPN is a separate heuristic ranking number, never a probability.
"""

from dataclasses import dataclass, field

from app.domain.catalog.resolver import ResolvedArchitecture
from app.domain.errors import DomainValidationError
from app.domain.units.guards import require_fraction
from app.schemas.analysis import ReliabilityAnalysis
from app.schemas.units import Provenance

MODEL_ID = "reliability-v1"
SEVERITY_MAX = 5
SPF_SEVERITY = 4
DEFAULT_DETECTABILITY = 3

RELIABILITY_ASSUMPTIONS: tuple[str, ...] = (
    "Failure modes and components are treated as statistically independent: "
    "R_system = product of component reliabilities.",
    "common-cause failures (shared radiation, thermal, software or power events) are not "
    "modelled, so nominal reliability is optimistic.",
    "Failure probabilities are illustrative gameplay estimates from the catalogue.",
    "risk_index is a per-mode mean: sum(probability x severity) / (5 x number of failure "
    "modes), range 0..1; adding benign (low-probability) modes dilutes it.",
    "Single-point failure: a component with a severity >= 4 failure mode and no mitigation "
    "resolving (by id or tag) to another selected component.",
)


def reliability(resolved: ResolvedArchitecture) -> ReliabilityAnalysis:
    comps = resolved.all_components()
    r_system = 1.0
    weighted = 0.0
    n_modes = 0
    spf: set[str] = set()
    for comp in comps:
        # Mitigation targets: ids and tags of the OTHER selected components only.
        others: set[str] = set()
        for other in comps:
            if other is not comp and other.id != comp.id:
                others.add(other.id)
                others.update(other.tags)
        for fm in comp.failure_modes:
            r_system *= 1.0 - fm.base_probability
            weighted += fm.base_probability * fm.severity
            n_modes += 1
            if fm.severity >= SPF_SEVERITY and not any(m in others for m in fm.mitigation_ids):
                spf.add(comp.id)
    risk = weighted / (SEVERITY_MAX * n_modes) if n_modes else 0.0
    return ReliabilityAnalysis(
        nominal_reliability=r_system,
        risk_index=risk,
        single_point_failures=sorted(spf),
    )


@dataclass(frozen=True)
class RpnResult:
    value: float
    occurrence: float
    severity: int
    detectability: int
    is_probability: bool = False
    label: str = "RPN (heuristic ranking number, not a probability)"
    provenance: Provenance = field(
        default_factory=lambda: Provenance(
            fidelity="gameplay-estimate",
            source_name="MISSIONFORGE FMEA heuristic",
            assumptions=(
                "RPN = occurrence x severity x detectability.",
                "The catalogue has no detectability data; the default of 3 is a gameplay estimate.",
            ),
        )
    )


def rpn(occurrence: float, severity: int, detectability: int = DEFAULT_DETECTABILITY) -> RpnResult:
    occ = require_fraction(occurrence, "occurrence")
    if not 1 <= severity <= SEVERITY_MAX:
        raise DomainValidationError("INVALID_SEVERITY", "severity", "severity must be 1..5")
    if not 1 <= detectability <= SEVERITY_MAX:
        raise DomainValidationError(
            "INVALID_DETECTABILITY", "detectability", "detectability must be 1..5"
        )
    return RpnResult(
        value=occ * severity * detectability,
        occurrence=occ,
        severity=severity,
        detectability=detectability,
    )
