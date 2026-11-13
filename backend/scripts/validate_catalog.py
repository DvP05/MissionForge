"""Catalogue validator: `python -m scripts.validate_catalog [catalog_dir]`.

Exits 1 on: schema error, unresolved compatible_with id, non-finite value, missing
provenance, duplicate ids, conflicting mass for the same id across files, or an illustrative
record that is not fidelity "gameplay-estimate". Exit 0 and a summary line otherwise.
"""

import sys
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.config import DEFAULT_CATALOG_DIR
from app.domain.catalog.loader import MANIFEST_NAME, read_json
from app.schemas.catalog import CatalogComponent

MASS_KEYS = ("mass", "dry_mass")


def _check_provenance(cid: str, raw: dict[str, Any], errors: list[str]) -> None:
    if not isinstance(raw.get("provenance"), dict):
        errors.append(f"MISSING_PROVENANCE {cid}: component has no provenance")
    params = raw.get("parameters")
    if isinstance(params, dict):
        for key, q in params.items():
            if not isinstance(q, dict) or not isinstance(q.get("provenance"), dict):
                errors.append(f"MISSING_PROVENANCE {cid}.{key}: quantity has no provenance")


def validate_catalog_dir(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        manifest = read_json(path / MANIFEST_NAME)
        files = list(manifest["files"])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return [f"MANIFEST {MANIFEST_NAME}: {exc}"]

    seen: dict[str, tuple[str, float | None]] = {}
    comps: list[CatalogComponent] = []
    for fname in files:
        try:
            doc = read_json(path / fname)
        except ValueError as exc:
            errors.append(f"NON_FINITE {fname}: {exc}")
            continue
        except OSError as exc:
            errors.append(f"SCHEMA {fname}: cannot read file ({exc})")
            continue
        raw_list = doc.get("components") if isinstance(doc, dict) else None
        if not isinstance(raw_list, list):
            errors.append(f"SCHEMA {fname}: expected an object with a 'components' list")
            continue
        for idx, raw in enumerate(raw_list):
            cid = str(raw.get("id", f"#{idx}")) if isinstance(raw, dict) else f"#{idx}"
            where = f"{fname}:{cid}"
            if not isinstance(raw, dict):
                errors.append(f"SCHEMA {where}: component is not an object")
                continue
            _check_provenance(where, raw, errors)
            try:
                comp = CatalogComponent.model_validate(raw)
            except ValidationError as exc:
                for e in exc.errors():
                    loc = ".".join(str(p) for p in e["loc"])
                    errors.append(f"SCHEMA {where}: {loc}: {e['msg']}")
                continue
            comps.append(comp)
            if comp.category != doc.get("category"):
                errors.append(f"SCHEMA {where}: category {comp.category!r} != file category")
            mass = next((comp.parameters[k].value for k in MASS_KEYS if k in comp.parameters), None)
            if comp.id in seen:
                prev_file, prev_mass = seen[comp.id]
                errors.append(f"DUPLICATE_ID {where}: also defined in {prev_file}")
                if prev_mass != mass:
                    errors.append(
                        f"CONFLICTING_MASS {where}: mass {mass} differs from {prev_mass} "
                        f"in {prev_file}"
                    )
            else:
                seen[comp.id] = (fname, mass)
            if comp.is_illustrative:
                bad = [] if comp.provenance.fidelity == "gameplay-estimate" else ["component"]
                bad += [
                    k for k, q in comp.parameters.items()
                    if q.provenance.fidelity != "gameplay-estimate"
                ]  # fmt: skip
                if bad:
                    errors.append(
                        f"ILLUSTRATIVE_FIDELITY {where}: not gameplay-estimate: {', '.join(bad)}"
                    )

    ids = {c.id: c.category for c in comps}
    for comp in comps:
        for rule in comp.compatible_with:
            for rid in rule.ids or []:
                if rid not in ids:
                    errors.append(f"UNRESOLVED_REFERENCE {comp.id}: compatible_with id {rid!r}")
                elif ids[rid] != rule.category:
                    errors.append(
                        f"UNRESOLVED_REFERENCE {comp.id}: {rid!r} is {ids[rid]!r}, "
                        f"rule says {rule.category!r}"
                    )
    return errors


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    path = Path(args[0]) if args else DEFAULT_CATALOG_DIR
    errors = validate_catalog_dir(path)
    if errors:
        for e in errors:
            print(e)
        print(f"catalogue validation FAILED: {len(errors)} error(s) in {path}")
        return 1
    print(f"catalogue OK: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
