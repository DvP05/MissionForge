"""R11: per-component failure modes are differentiated and well-formed."""

from app.config import DEFAULT_CATALOG_DIR
from app.domain.catalog.loader import load_catalog

# Vocabulary documented in data/catalog/README.md.
METRICS = {
    "battery_soc", "link_margin", "pointing_error", "data_buffer", "delta_v", "power_margin",
    "mass_margin", "launch_mass_margin", "thermal_margin", "schedule_margin", "cost_margin",
    "science_return",
}  # fmt: skip


def test_failure_modes_are_differentiated_and_resolvable() -> None:
    catalog = load_catalog(DEFAULT_CATALOG_DIR)
    comps = list(catalog.values())
    ids = {c.id for c in comps}
    tags = {t for c in comps for t in c.tags}
    descriptions: list[str] = []
    for c in comps:
        assert c.failure_modes, c.id
        for fm in c.failure_modes:
            descriptions.append(fm.description)
            assert fm.affected_metric in METRICS, (c.id, fm.affected_metric)
            assert 1 <= fm.severity <= 5
            assert 0 < fm.base_probability < 1
            for mid in fm.mitigation_ids:
                assert mid in ids | tags, (c.id, mid)
    assert len(descriptions) == len(set(descriptions))
    assert len(comps) >= 30


def test_prop_biprop_is_smallsat_scale() -> None:
    biprop = load_catalog(DEFAULT_CATALOG_DIR).get("prop-biprop")
    assert biprop.parameters["propellant_capacity"].value <= 40.0
