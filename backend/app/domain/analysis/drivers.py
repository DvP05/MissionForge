"""Top constraint drivers (architecture 7.11 step 6). Pure and deterministic."""

from collections.abc import Sequence

from app.schemas.analysis import ConstraintResult

MAX_DRIVERS = 5


def top_drivers(constraints: Sequence[ConstraintResult]) -> list[str]:
    """Ids of failed then warning constraints.

    Ordered by severity (desc), then |margin_fraction| ascending (a missing margin sorts
    last), then id. Capped at ``MAX_DRIVERS``.
    """
    bad = [c for c in constraints if c.status in ("fail", "warning")]
    # fail outranks warning even if a warning carries a higher severity number
    bad.sort(
        key=lambda c: (
            c.status != "fail",
            -c.severity,
            abs(c.margin_fraction) if c.margin_fraction is not None else float("inf"),
            c.id,
        )
    )
    return [c.id for c in bad[:MAX_DRIVERS]]
