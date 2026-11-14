"""Mission Analyst: deterministic recommendations (architecture 19.8, Task 6.8).

Every number in a recommendation is a fresh engine result for the mutated design. No
language model is involved; an optional LLM may only rephrase these findings later.
"""

from app.domain.analyst.explain_constraint import explain_constraint
from app.domain.analyst.recommend_mutations import (
    MAX_RECOMMENDATIONS,
    apply_mutation,
    recommend,
)

__all__ = ["MAX_RECOMMENDATIONS", "apply_mutation", "explain_constraint", "recommend"]
