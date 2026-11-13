import json
import math
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from app.config import DEFAULT_CATALOG_DIR
from app.domain.catalog.loader import Catalog, load_catalog
from app.domain.catalog.resolver import CatalogItemNotFound, resolve_architecture
from app.domain.mission.validation import CatalogLookup
from app.schemas.catalog import CatalogComponent
from app.schemas.mission import SpacecraftArchitecture
from scripts import validate_catalog

CATEGORIES = [
    "launch", "bus", "propulsion", "power", "adcs", "communications",
    "thermal", "cdh", "instrument", "ground",
]  # fmt: skip
REQUIRED_KEYS = {
    "launch": {"launch_mass_limit", "cost"},
    "bus": {"mass", "structure_mass", "power_w", "cost", "max_payload_mass"},
    "propulsion": {"dry_mass", "isp", "power_w", "propellant_capacity", "cost"},
    "power": {"mass", "array_power_at_1au", "battery_capacity", "usable_dod",
              "eps_efficiency", "cost"},
    "adcs": {"mass", "power_w", "pointing_accuracy", "cost"},
    "communications": {"mass", "tx_power", "antenna_gain", "frequency", "required_ebn0",
                       "implementation_loss", "max_data_rate", "power_w", "cost"},
    "thermal": {"mass", "power_w", "cost"},
    "cdh": {"mass", "power_w", "storage", "cost"},
    "instrument": {"mass", "power_w", "data_rate", "pointing_requirement", "cost"},
    "ground": {"station_gain", "noise_temperature", "contact_availability", "cost"},
}  # fmt: skip
VOCAB = {
    "visible-imaging", "shape-model", "vnir-spectroscopy", "thermal-infrared",
    "magnetometry", "plasma-environment", "high-res-imaging", "multispectral-imaging",
}  # fmt: skip
FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "catalog_broken"


@pytest.fixture(scope="module")
def catalog() -> Catalog:
    return load_catalog(DEFAULT_CATALOG_DIR)


def test_manifest_and_files() -> None:
    manifest = json.loads((DEFAULT_CATALOG_DIR / "catalog_manifest.json").read_text("utf-8"))
    assert manifest["catalogVersion"] == "0.1.0"
    assert manifest["generatedAt"]
    assert sorted(manifest["files"]) == sorted(f"{c}.json" for c in CATEGORIES)
    assert "audit" in manifest["note"]


def test_version_and_lookup_protocol(catalog: Catalog) -> None:
    assert catalog.version == "0.1.0"
    lookup: CatalogLookup = catalog
    assert lookup.has("bus-12u") and not lookup.has("nope")
    assert catalog.get("bus-12u") is not None
    assert catalog.get("nope") is None


@pytest.mark.parametrize("cat", CATEGORIES)
def test_category_contents(catalog: Catalog, cat: str) -> None:
    comps = catalog.by_category(cat)
    assert (4 if cat == "instrument" else 3) <= len(comps) <= 5
    for c in comps:
        assert isinstance(c, CatalogComponent)
        assert c.category == cat
        assert set(c.parameters) >= REQUIRED_KEYS[cat]
        assert c.name.startswith("Archetype:")


def test_every_value_finite_with_gameplay_estimate_provenance(catalog: Catalog) -> None:
    for c in catalog.values():
        assert c.is_illustrative
        assert c.provenance.fidelity == "gameplay-estimate" and c.provenance.assumptions
        for k, q in c.parameters.items():
            assert math.isfinite(q.value), (c.id, k)
            assert q.unit
            assert q.provenance.fidelity == "gameplay-estimate", (c.id, k)
            assert q.provenance.assumptions, (c.id, k)


def test_compatible_with_ids_resolve(catalog: Catalog) -> None:
    for c in catalog.values():
        for rule in c.compatible_with:
            for rid in rule.ids or []:
                assert catalog.has(rid), (c.id, rid)
                assert catalog[rid].category == rule.category


def test_instrument_vocabulary(catalog: Catalog) -> None:
    caps = {cap for c in catalog.by_category("instrument") for cap in c.capabilities}
    assert caps == VOCAB
    rates = sorted(c.parameters["data_rate"].value for c in catalog.by_category("instrument"))
    assert rates[-1] >= 5 * rates[-2]  # one deliberately high data rate


def test_comms_has_weak_and_strong(catalog: Catalog) -> None:
    comms = catalog.by_category("communications")
    rates = sorted(c.parameters["max_data_rate"].value for c in comms)
    assert rates[-1] >= 100 * rates[0]
    gains = sorted(c.parameters["antenna_gain"].value for c in comms)
    assert gains[-1] - gains[0] >= 20


def test_catalog_is_immutable(catalog: Catalog) -> None:
    with pytest.raises(TypeError):
        catalog["x"] = catalog["bus-12u"]  # type: ignore[index]
    assert isinstance(catalog.by_category("bus"), tuple)


def _arch(**over: object) -> SpacecraftArchitecture:
    base: dict[str, object] = {
        "launch_vehicle_id": "launch-rideshare-leo", "bus_id": "bus-12u",
        "propulsion_id": "prop-monoprop", "power_id": "power-medium", "adcs_id": "adcs-fine",
        "communications_id": "comms-xband-lowgain", "thermal_id": "thermal-heaters",
        "cdh_id": "cdh-standard", "ground_segment_id": "ground-medium",
        "instrument_ids": ("inst-wide-camera", "inst-magnetometer"),
    }  # fmt: skip
    base.update(over)
    return SpacecraftArchitecture.model_validate(base)


def test_resolve_architecture(catalog: Catalog) -> None:
    r = resolve_architecture(_arch(), catalog)
    assert r.bus.id == "bus-12u" and r.ground.id == "ground-medium"
    assert [i.id for i in r.instruments] == ["inst-wide-camera", "inst-magnetometer"]
    assert len(r.all_components()) == 11


def test_resolve_unknown_raises(catalog: Catalog) -> None:
    with pytest.raises(CatalogItemNotFound) as ei:
        resolve_architecture(_arch(bus_id="bus-zzz"), catalog)
    assert ei.value.code == "CATALOG_ITEM_NOT_FOUND"
    with pytest.raises(CatalogItemNotFound):
        resolve_architecture(_arch(instrument_ids=("inst-nope",)), catalog)


def test_validator_passes_on_default_catalog() -> None:
    assert validate_catalog.validate_catalog_dir(DEFAULT_CATALOG_DIR) == []
    assert validate_catalog.main([]) == 0


def test_validator_fails_on_broken_fixture(capsys: pytest.CaptureFixture[str]) -> None:
    errors = validate_catalog.validate_catalog_dir(FIXTURE)
    assert any("UNRESOLVED_REFERENCE" in e and "bus-does-not-exist" in e for e in errors)
    assert validate_catalog.main([str(FIXTURE)]) == 1
    assert "UNRESOLVED_REFERENCE" in capsys.readouterr().out


def _copy_catalog(dest: Path) -> Path:
    dest.mkdir(parents=True)
    for f in DEFAULT_CATALOG_DIR.glob("*.json"):
        (dest / f.name).write_text(f.read_text("utf-8"), encoding="utf-8")
    return dest


def _mutate(dest: Path, fname: str, fn: Callable[[dict[str, Any]], None]) -> list[str]:
    d = _copy_catalog(dest)
    doc = json.loads((d / fname).read_text("utf-8"))
    fn(doc)
    (d / fname).write_text(json.dumps(doc), encoding="utf-8")
    return validate_catalog.validate_catalog_dir(d)


def test_validator_detects_each_defect(tmp_path: Path) -> None:
    def drop_prov(doc: dict[str, Any]) -> None:
        del doc["components"][0]["parameters"]["mass"]["provenance"]

    assert any("MISSING_PROVENANCE" in e for e in _mutate(tmp_path / "a", "bus.json", drop_prov))

    def not_gp(doc: dict[str, Any]) -> None:
        doc["components"][0]["provenance"]["fidelity"] = "source-backed"

    assert any("ILLUSTRATIVE_FIDELITY" in e for e in _mutate(tmp_path / "b", "bus.json", not_gp))

    def dup(doc: dict[str, Any]) -> None:
        c = json.loads(json.dumps(doc["components"][0]))
        c["parameters"]["mass"]["value"] = 999.0
        doc["components"].append(c)

    errs = _mutate(tmp_path / "c", "bus.json", dup)
    assert any("DUPLICATE_ID" in e for e in errs)
    assert any("CONFLICTING_MASS" in e for e in errs)

    d = _copy_catalog(tmp_path / "d")
    text = (d / "bus.json").read_text("utf-8")
    assert '"value": 20.0' in text
    (d / "bus.json").write_text(text.replace('"value": 20.0', '"value": NaN', 1), encoding="utf-8")
    assert any("NON_FINITE" in e for e in validate_catalog.validate_catalog_dir(d))

    def bad_schema(doc: dict[str, Any]) -> None:
        doc["components"][0]["parameters"]["mass"]["unit"] = "furlong"

    assert any("SCHEMA" in e for e in _mutate(tmp_path / "e", "bus.json", bad_schema))


@pytest.mark.skip(reason="Task 2.8: assert instrument/antenna/battery swap changes mass analysis")
def test_component_swap_changes_mass_analysis() -> None:
    raise AssertionError("implemented in Task 2.8")
