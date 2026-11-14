"""Mission Design Arena: candidates, Pareto front and archetypes (19.2, Task 6.2, M10).

A deterministic O(n^2) non-dominated filter over a bounded, seeded candidate pool. This is
not NSGA-II; objective weights are for display only and never used for dominance.
"""

from app.domain.optimization.dominates import dominates, pareto_front
from app.domain.optimization.generate_candidates import (
    MAX_CANDIDATES,
    MIN_CANDIDATES,
    CandidateDesign,
    candidate_id,
    generate_candidates,
)
from app.domain.optimization.optimize import OBJECTIVES, optimize
from app.domain.optimization.select_archetypes import select_archetypes

__all__ = [
    "MAX_CANDIDATES",
    "MIN_CANDIDATES",
    "OBJECTIVES",
    "CandidateDesign",
    "candidate_id",
    "dominates",
    "generate_candidates",
    "optimize",
    "pareto_front",
    "select_archetypes",
]
