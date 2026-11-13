"""Shared builders for cost/reliability/thermal tests."""

from typing import Any

from app.domain.catalog.resolver import ResolvedArchitecture
from app.schemas.catalog import CatalogComponent

PROV = {"fidelity": "gameplay-estimate", "source_name": "t", "assumptions": ["t"]}


def comp(
    cid: str,
    cat: str,
    cost: float | None = None,
    modes: list[dict[str, Any]] | None = None,
    caps: list[str] | None = None,
) -> CatalogComponent:
    params: dict[str, Any] = {}
    if cost is not None:
        params["cost"] = {"value": cost, "unit": "USD", "provenance": PROV}
    return CatalogComponent.model_validate(
        {
            "id": cid, "name": cid, "category": cat, "description": "d",
            "parameters": params, "capabilities": caps or [],
            "failure_modes": modes or [],
            "source_record_id": "s", "provenance": PROV, "is_illustrative": True,
        }
    )  # fmt: skip


def mode(mid: str, p: float, sev: int, mitigations: list[str] | None = None) -> dict[str, Any]:
    return {
        "id": mid, "description": mid, "base_probability": p, "affected_metric": "x",
        "severity": sev, "mitigation_ids": mitigations or [],
    }  # fmt: skip


def arch(**over: CatalogComponent | tuple[CatalogComponent, ...]) -> ResolvedArchitecture:
    base: dict[str, Any] = {
        "launch": comp("l", "launch", 1_000_000.0),
        "bus": comp("bus", "bus", 2_000_000.0),
        "propulsion": comp("prop", "propulsion", 500_000.0),
        "power": comp("pow", "power", 300_000.0),
        "adcs": comp("adcs", "adcs", 200_000.0),
        "communications": comp("comm", "communications", 400_000.0),
        "thermal": comp("therm", "thermal", 100_000.0),
        "cdh": comp("cdh", "cdh", 150_000.0),
        "ground": comp("g", "ground", 365_250.0),
        "instruments": (comp("inst", "instrument", 250_000.0),) * 2,
    }
    base.update(over)
    return ResolvedArchitecture(**base)
