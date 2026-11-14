"""Trade-study metric deltas (architecture 8.4, F-019).

Pure function over two ``MissionAnalysis`` results: delta = alternative - base, in the metric's
SI-style unit (``TRADE_METRICS``). A metric is omitted (never reported as 0) when either side
is a placeholder, i.e. the analysis failed (``catalog-item-not-found`` / ``model-input-invalid``)
or the Quantity is labelled ``not-modelled``. Mass allocation margin is not a trade metric.
"""

from collections.abc import Callable
from dataclasses import dataclass

from app.schemas.analysis import MissionAnalysis
from app.schemas.units import Quantity

FAILURE_CONSTRAINT_IDS = frozenset({"catalog-item-not-found", "model-input-invalid"})


@dataclass(frozen=True)
class TradeMetric:
    key: str
    label: str
    unit: str
    read: Callable[[MissionAnalysis], float | None]  # None => not defined for this analysis


def analysis_failed(analysis: MissionAnalysis) -> bool:
    """True when the engine could not run and every number is a placeholder."""
    return any(c.id in FAILURE_CONSTRAINT_IDS for c in analysis.constraints)


def _scalar(read: Callable[[MissionAnalysis], float]) -> Callable[[MissionAnalysis], float | None]:
    return lambda a: None if analysis_failed(a) else read(a)


def _quantity(
    read: Callable[[MissionAnalysis], Quantity],
) -> Callable[[MissionAnalysis], float | None]:
    def inner(a: MissionAnalysis) -> float | None:
        q = read(a)
        if analysis_failed(a) or q.provenance.fidelity == "not-modelled":
            return None
        return q.value

    return inner


TRADE_METRICS: tuple[TradeMetric, ...] = (
    TradeMetric("dry_mass_kg", "Dry mass", "kg", _quantity(lambda a: a.budgets.dry_mass_kg)),
    TradeMetric("wet_mass_kg", "Wet mass", "kg", _quantity(lambda a: a.budgets.wet_mass_kg)),
    TradeMetric(
        "average_power_w", "Average power", "W", _quantity(lambda a: a.budgets.average_power_w)
    ),
    TradeMetric("peak_power_w", "Peak power", "W", _quantity(lambda a: a.budgets.peak_power_w)),
    TradeMetric(
        "data_generated_bit",
        "Data generated",
        "bit",
        _quantity(lambda a: a.budgets.data_generated_bits),
    ),
    TradeMetric(
        "data_downlinked_bit",
        "Data downlinked",
        "bit",
        _quantity(lambda a: a.budgets.data_downlinked_bits),
    ),
    TradeMetric(
        "delta_v_margin_km_per_s",
        "Delta-v margin",
        "km/s",
        _scalar(lambda a: a.budgets.delta_v_margin_km_per_s),
    ),
    TradeMetric(
        "estimated_cost_usd",
        "Estimated cost",
        "USD",
        _quantity(lambda a: a.budgets.estimated_cost_usd),
    ),
    TradeMetric(
        "science_coverage_score",
        "Science coverage score",
        "%",
        _scalar(lambda a: a.science.coverage_score),
    ),
    TradeMetric("total_score", "Total score", "points", _scalar(lambda a: a.score.total)),
)


def compute_deltas(base: MissionAnalysis, alt: MissionAnalysis) -> dict[str, float]:
    """Per-metric ``alt - base``; metrics undefined on either side are omitted."""
    out: dict[str, float] = {}
    for metric in TRADE_METRICS:
        b, a = metric.read(base), metric.read(alt)
        if b is not None and a is not None:
            out[metric.key] = a - b
    return out
