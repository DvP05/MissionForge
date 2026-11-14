"""Default detector configurations, one per telemetry channel (gameplay-estimate)."""

from typing import Literal

from app.schemas.health import DetectorConfig

Category = Literal["power-thermal", "attitude-pointing", "comms-data", "propulsion"]

DETECTORS: tuple[tuple[DetectorConfig, Category, tuple[str, ...]], ...] = (
    (
        DetectorConfig(
            channel="battery_soc", unit="fraction", expected=1.0, warn=0.05, crit=0.15,
            persistence_k=2, hard_limit=0.2, lam=0.5,
            rationale="A battery running 5 points below the nominal model for two checkpoints "
            "is worth a look; 15 points, or under 20% charge, risks the spacecraft.",
        ),
        "power-thermal", ("power",),
    ),
    (
        DetectorConfig(
            channel="pointing_error_deg", unit="deg", expected=0.0, warn=0.02, crit=0.1,
            persistence_k=2, hard_limit=None, lam=0.5,
            rationale="Pointing drifting from the ADCS model blurs observations.",
        ),
        "attitude-pointing", ("adcs",),
    ),
    (
        DetectorConfig(
            channel="link_margin_db", unit="dB", expected=0.0, warn=1.0, crit=3.0,
            persistence_k=2, hard_limit=None, lam=0.5,
            rationale="A link 1 dB worse than modelled for two passes eats the margin; "
            "3 dB loses the pass.",
        ),
        "comms-data", ("communications", "ground"),
    ),
    (
        DetectorConfig(
            channel="buffer_fill", unit="fraction", expected=0.0, warn=0.05, crit=0.2,
            persistence_k=2, hard_limit=1.0, lam=0.5,
            rationale="Storage filling faster than planned means data waits too long for "
            "a downlink; a full buffer loses data.",
        ),
        "comms-data", ("cdh", "communications"),
    ),
    (
        DetectorConfig(
            channel="propellant_fraction", unit="fraction", expected=1.0, warn=0.02,
            crit=0.1, persistence_k=2, hard_limit=0.0, lam=0.5,
            rationale="Propellant below the planned use points to an unplanned burn or leak.",
        ),
        "propulsion", ("propulsion",),
    ),
)  # fmt: skip
