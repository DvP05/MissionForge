"""Mission Analyst recommendation contracts (architecture 19.8). Owner: domain lead.

Recommendations are produced deterministically (one-step mutations + sensitivity over the
same engine). An optional LLM may only rephrase them; it never creates numbers or IDs.
"""

from typing import Literal

from pydantic import Field

from app.schemas.api import ContractModel
from app.schemas.units import FiniteFloat, Scalar

MutationKind = Literal[
    "swap-component", "add-instrument", "remove-instrument", "change-operations"
]  # fmt: skip
ConfidenceLabel = Literal["high", "medium", "low"]


class DesignMutation(ContractModel):
    kind: MutationKind
    target: str  # allow-listed MissionState path or component slot; never evaluated
    from_value: Scalar | None = None
    to_value: Scalar | None = None
    description: str


class Recommendation(ContractModel):
    id: str
    mutation: DesignMutation
    metric_before: dict[str, FiniteFloat]
    metric_after: dict[str, FiniteFloat]
    tradeoffs: list[str]
    confidence_label: ConfidenceLabel
    source_refs: list[str] = Field(default_factory=list)  # evidence / constraint ids
    explanation: str
