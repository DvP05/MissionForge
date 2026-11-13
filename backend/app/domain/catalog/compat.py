"""Catalogue compatibility checks.

A component's `compatible_with` rules constrain the other selected components of the named
category: every selected component of that category must match at least one of the rules
for that category (rules of one category are alternatives). A rule matches by `ids`
(membership) and/or `tags` (any overlap); a rule with neither matches anything. Rules for a
category with no selected component are ignored.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from app.schemas.catalog import CatalogComponent, CompatibilityRule


@dataclass(frozen=True)
class CompatibilityIssue:
    code: str
    component_id: str
    message: str


def _matches(rule: CompatibilityRule, other: CatalogComponent) -> bool:
    if rule.ids is not None and other.id not in rule.ids:
        return False
    return not (rule.tags is not None and not set(rule.tags) & set(other.tags))


def check_compatibility(components: Sequence[CatalogComponent]) -> list[CompatibilityIssue]:
    issues: list[CompatibilityIssue] = []
    for comp in components:
        categories = {r.category for r in comp.compatible_with}
        for category in sorted(categories):
            rules = [r for r in comp.compatible_with if r.category == category]
            for other in components:
                if other.category != category or other.id == comp.id:
                    continue
                if not any(_matches(r, other) for r in rules):
                    issues.append(
                        CompatibilityIssue(
                            code="INCOMPATIBLE",
                            component_id=comp.id,
                            message=(f"{comp.id} is not compatible with {category} {other.id}"),
                        )
                    )
    return issues
