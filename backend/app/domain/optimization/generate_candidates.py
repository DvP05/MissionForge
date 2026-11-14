"""Bounded, deterministic candidate pool (architecture 19.2 step 1).

Order: baseline, every single catalogue swap, instrument add/remove/swap edits, then
two-way swaps built on caller-chosen "anchor" changes (for example a radio upgrade that
fixes a failing link), then the remaining room split between a seeded sample of other
two-way swaps (generation 2) and seeded whole-design combinations (generation 3).
Ids are content hashes of the architecture, so the same design always gets the same id,
whatever order it was generated in.
"""

import hashlib
import json
import random
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import combinations

from app.domain.catalog.loader import Catalog
from app.domain.errors import DomainValidationError
from app.schemas.mission import MissionState, SpacecraftArchitecture

MIN_CANDIDATES = 1
MAX_CANDIDATES = 250

# Catalogue category -> SpacecraftArchitecture field (single-select parts).
SINGLE_FIELDS: tuple[tuple[str, str], ...] = (
    ("launch", "launch_vehicle_id"),
    ("bus", "bus_id"),
    ("propulsion", "propulsion_id"),
    ("power", "power_id"),
    ("adcs", "adcs_id"),
    ("communications", "communications_id"),
    ("thermal", "thermal_id"),
    ("cdh", "cdh_id"),
    ("ground", "ground_segment_id"),
)


@dataclass(frozen=True)
class Change:
    category: str
    from_id: str | None
    to_id: str | None

    def describe(self) -> str:
        if self.from_id is None:
            return f"Add instrument {self.to_id}"
        if self.to_id is None:
            return f"Remove instrument {self.from_id}"
        return f"Swap {self.category}: {self.from_id} to {self.to_id}"


@dataclass(frozen=True)
class CandidateDesign:
    id: str
    state: MissionState
    generation: int  # 0 baseline, 1 one change, 2 two changes, 3 sampled combination
    changes: tuple[Change, ...]


def candidate_id(arch: SpacecraftArchitecture) -> str:
    payload = json.dumps(arch.model_dump(mode="json"), sort_keys=True)
    return "cand-" + hashlib.sha256(payload.encode()).hexdigest()[:12]


def _apply(base: MissionState, changes: tuple[Change, ...]) -> MissionState:
    update: dict[str, object] = {}
    instruments = list(base.architecture.instrument_ids)
    for ch in changes:
        if ch.category == "instrument":
            if ch.from_id is not None:
                instruments = [i for i in instruments if i != ch.from_id]
            if ch.to_id is not None and ch.to_id not in instruments:
                instruments.append(ch.to_id)
        else:
            field = dict(SINGLE_FIELDS)[ch.category]
            update[field] = ch.to_id
    update["instrument_ids"] = tuple(instruments)
    arch = base.architecture.model_copy(update=update)
    return base.model_copy(update={"architecture": arch})


def single_changes(base: MissionState, catalog: Catalog) -> list[Change]:
    """Every one-part swap plus instrument add / remove / swap edits, in a fixed order."""
    return _single_changes(base, catalog)


def _single_changes(base: MissionState, catalog: Catalog) -> list[Change]:
    arch = base.architecture
    out: list[Change] = []
    for category, field in SINGLE_FIELDS:
        current = str(getattr(arch, field))
        for comp in catalog.by_category(category):
            if comp.id != current:
                out.append(Change(category, current, comp.id))
    selected = list(dict.fromkeys(arch.instrument_ids))
    others = [c.id for c in catalog.by_category("instrument") if c.id not in selected]
    out += [Change("instrument", None, i) for i in others]
    if len(selected) > 1:  # never remove the last instrument
        out += [Change("instrument", i, None) for i in selected]
    out += [Change("instrument", i, j) for i in selected for j in others]
    return out


def _compatible_pair(a: Change, b: Change) -> bool:
    if a.category != b.category:
        return True
    # Two instrument edits are fine unless they touch the same instrument.
    if a.category != "instrument":
        return False
    touched_a = {a.from_id, a.to_id} - {None}
    touched_b = {b.from_id, b.to_id} - {None}
    return not touched_a & touched_b


def generate_candidates(
    base: MissionState,
    catalog: Catalog,
    *,
    seed: int,
    cap: int,
    anchors: Sequence[Change] = (),
) -> list[CandidateDesign]:
    """Up to `cap` distinct designs (fewer when fewer legal combinations exist)."""
    if not MIN_CANDIDATES <= cap <= MAX_CANDIDATES:
        raise DomainValidationError(
            "INVALID_CANDIDATE_CAP", "cap", f"cap must be within {MIN_CANDIDATES}..{MAX_CANDIDATES}"
        )
    out: dict[str, CandidateDesign] = {}

    def add(changes: tuple[Change, ...], generation: int) -> None:
        if len(out) >= cap:
            return
        state = _apply(base, changes) if changes else base
        cid = candidate_id(state.architecture)
        if cid not in out:
            out[cid] = CandidateDesign(cid, state, generation, changes)

    add((), 0)
    singles = _single_changes(base, catalog)
    for ch in singles:
        add((ch,), 1)
    for anchor in anchors:
        for other in singles:
            if other != anchor and _compatible_pair(anchor, other):
                add((anchor, other), 2)
    rng = random.Random(seed)
    pairs = [(a, b) for a, b in combinations(singles, 2) if _compatible_pair(a, b)]
    rng.shuffle(pairs)
    pair_quota = len(out) + (cap - len(out) + 1) // 2
    for a, b in pairs:
        if len(out) >= pair_quota:
            break
        add((a, b), 2)
    attempts = 0
    while len(out) < cap and attempts < cap * 20:
        attempts += 1
        add(_random_combination(base, catalog, rng), 3)
    for a, b in pairs:  # top up with pairs if sampling ran out of new designs
        if len(out) >= cap:
            break
        add((a, b), 2)
    return list(out.values())


def _random_combination(
    base: MissionState, catalog: Catalog, rng: random.Random
) -> tuple[Change, ...]:
    """Every single-select part drawn at random, plus 1-3 random instruments."""
    arch = base.architecture
    changes: list[Change] = []
    for category, field in SINGLE_FIELDS:
        options = [c.id for c in catalog.by_category(category)]
        if not options:
            continue
        pick = rng.choice(options)
        current = str(getattr(arch, field))
        if pick != current:
            changes.append(Change(category, current, pick))
    instruments = [c.id for c in catalog.by_category("instrument")]
    if instruments:
        chosen = rng.sample(instruments, rng.randint(1, min(3, len(instruments))))
        selected = list(dict.fromkeys(arch.instrument_ids))
        changes += [Change("instrument", i, None) for i in selected if i not in chosen]
        changes += [Change("instrument", None, i) for i in chosen if i not in selected]
    return tuple(changes)
