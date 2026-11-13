from app.domain.catalog.compat import CompatibilityIssue, check_compatibility
from app.schemas.catalog import CatalogComponent

PROV = {"fidelity": "gameplay-estimate", "source_name": "t", "assumptions": ["t"]}


def comp(
    cid: str, cat: str, tags: list[str] | None = None, compat: list[dict[str, object]] | None = None
) -> CatalogComponent:
    return CatalogComponent.model_validate(
        {
            "id": cid, "name": cid, "category": cat, "description": "d", "tags": tags or [],
            "parameters": {}, "compatible_with": compat or [], "source_record_id": "s",
            "provenance": PROV, "is_illustrative": True,
        }
    )  # fmt: skip


def test_no_rules_no_issues() -> None:
    assert check_compatibility([comp("a", "bus"), comp("b", "adcs")]) == []


def test_tag_rule_satisfied_and_violated() -> None:
    needs = comp("c", "communications", compat=[{"category": "bus", "tags": ["large"]}])
    assert check_compatibility([needs, comp("b", "bus", tags=["large"])]) == []
    issues = check_compatibility([needs, comp("b", "bus", tags=["small"])])
    assert len(issues) == 1
    assert issues[0] == CompatibilityIssue(
        code="INCOMPATIBLE", component_id="c", message=issues[0].message
    )
    assert "b" in issues[0].message


def test_id_rule() -> None:
    needs = comp("i", "instrument", compat=[{"category": "bus", "ids": ["bus-x"]}])
    assert check_compatibility([needs, comp("bus-x", "bus")]) == []
    assert len(check_compatibility([needs, comp("bus-y", "bus")])) == 1


def test_rules_for_absent_category_ignored() -> None:
    needs = comp("i", "instrument", compat=[{"category": "bus", "ids": ["bus-x"]}])
    assert check_compatibility([needs]) == []


def test_multiple_rules_same_category_are_or() -> None:
    needs = comp(
        "i",
        "instrument",
        compat=[{"category": "bus", "ids": ["bus-x"]}, {"category": "bus", "tags": ["big"]}],
    )
    assert check_compatibility([needs, comp("bus-y", "bus", tags=["big"])]) == []
