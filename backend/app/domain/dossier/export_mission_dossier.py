"""Evidence Passport v1: evidence ledger plus the exportable JSON package and HTML report.

Pure (architecture 19.9, M18, prod 21.4): the export time, app version, analysis and replay
check are passed in; the HTML is rendered by `render_html`. The output is deterministic: the
same inputs give byte-identical JSON and HTML. In the route, `exported_at` is also the time the
budgets are recomputed, so `exportedAt` and `latestAnalysis.calculatedAt` both vary with the
export time and nothing else does.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlsplit

from app.domain.dossier.render_html import (
    BUDGET_QUANTITIES,
    NON_ENDORSEMENT,
    ReplayCheck,
    render_html,
)
from app.schemas.analysis import MissionAnalysis
from app.schemas.catalog import CatalogComponent
from app.schemas.evidence import (
    EvidenceRecord,
    MissionPackage,
    MissionPackageManifest,
    ResearchEvidence,
)
from app.schemas.simulation import MissionRun
from app.schemas.space_data import JplMissionOption
from app.schemas.units import Fidelity, Provenance, Unit

__all__ = [
    "NON_ENDORSEMENT",
    "Dossier",
    "ReplayCheck",
    "build_evidence_records",
    "export_mission_dossier",
]

UNAVAILABLE_NO_AUDIT = "unavailable-source: no primary source audited yet"
ENGINE_SOURCE = "MISSIONFORGE simulation engine"
JPL_API_HOST = "ssd-api.jpl.nasa.gov"
_FIDELITY_RANK: dict[str, int] = {
    "not-modelled": 0,
    "gameplay-estimate": 1,
    "derived": 2,
    "source-backed": 3,
}


@dataclass(frozen=True)
class Dossier:
    package: MissionPackage
    html: str


# ---- Evidence ledger ----------------------------------------------------------------------


def _limitations(fidelity: Fidelity, url: str | None, *extra: str) -> list[str]:
    out: list[str] = []
    if fidelity != "derived" and not _is_http(url):
        out.append(UNAVAILABLE_NO_AUDIT)
    if fidelity == "gameplay-estimate":
        out.append("Gameplay estimate; not a verified specification.")
    out.extend(extra)
    return out


def _from_provenance(
    rid: str,
    subject: str,
    pv: Provenance,
    unit: Unit | None,
    *extra: str,
    conversion: str | None = None,
) -> EvidenceRecord:
    return EvidenceRecord(
        id=rid,
        subject_id=subject,
        fidelity=pv.fidelity,
        source_title=pv.source_name,
        source_url=pv.source_url if _is_http(pv.source_url) else None,
        source_version=pv.source_version,
        retrieved_at=pv.retrieved_at,
        published_at=pv.published_at,
        unit=unit,
        conversion_notes=conversion or pv.notes,
        assumptions=list(pv.assumptions),
        limitations=_limitations(pv.fidelity, pv.source_url, *extra),
    )


def _architecture_ids(run: MissionRun) -> list[str]:
    a = run.input_snapshot.architecture
    ids = [
        a.launch_vehicle_id, a.bus_id, a.propulsion_id, a.power_id, a.adcs_id,
        a.communications_id, a.thermal_id, a.cdh_id, *a.instrument_ids, a.ground_segment_id,
    ]  # fmt: skip
    out: list[str] = []
    for cid in ids:
        if cid not in out:
            out.append(cid)
    return out


def _component_records(
    run: MissionRun, catalog: Mapping[str, CatalogComponent], catalog_version: str
) -> list[EvidenceRecord]:
    out: list[EvidenceRecord] = []
    for cid in _architecture_ids(run):
        comp = catalog.get(cid)
        if comp is None:
            out.append(
                EvidenceRecord(
                    id=f"ev-component-{cid}",
                    subject_id=cid,
                    fidelity="not-modelled",
                    source_title="Not in this catalogue",
                    source_version=catalog_version,
                    limitations=[
                        f"unavailable-source: component not found in catalogue {catalog_version}",
                        "Its parameters cannot be shown or re-derived by this server.",
                    ],
                )
            )
            continue
        extra = ("Illustrative archetype, not a real product (is_illustrative).",)
        for name in sorted(comp.parameters):
            q = comp.parameters[name]
            out.append(
                _from_provenance(
                    f"ev-component-{cid}-{name}",
                    f"{cid}.{name}",
                    q.provenance,
                    q.unit,
                    *(extra if comp.is_illustrative else ()),
                )
            )
    return out


_TRAJECTORY_FIELDS: tuple[tuple[str, Unit | None], ...] = (
    ("time_of_flight_days", "day"),
    ("c3_km2_per_s2", None),
    ("departure_v_infinity_km_per_s", "km/s"),
    ("arrival_v_infinity_km_per_s", "km/s"),
    ("mission_delta_v_km_per_s", "km/s"),
)


def _is_http(url: str | None) -> bool:
    return bool(url) and str(url).startswith(("https://", "http://"))


def _jpl_link(ref: str | None) -> str | None:
    """A link only for a plain https URL on the JPL API host (still not verified).

    Rejects backslashes (browsers read them as "/"), whitespace and control characters,
    userinfo and ports, then emits a URL rebuilt from the host plus path and query only.
    """
    if not ref or any(c == "\\" or c.isspace() or ord(c) < 32 or ord(c) == 127 for c in ref):
        return None
    try:
        parts = urlsplit(ref)
        host, user, password, port = parts.hostname, parts.username, parts.password, parts.port
    except ValueError:
        return None
    if parts.scheme != "https" or host != JPL_API_HOST:
        return None
    if user is not None or password is not None or port is not None or "@" in parts.netloc:
        return None
    return f"https://{JPL_API_HOST}{parts.path}" + (f"?{parts.query}" if parts.query else "")


CLAIMED_JPL = "claimed JPL source — not verified by this server"


def _client_claim_notes(ref: str | None, link: str | None) -> list[str]:
    """Assumption text for a client-supplied reference that is not shown as a link."""
    return [f"Claimed reference (unverified, plain text): {ref}"] if ref and link is None else []


def _verified_records(run: MissionRun, option: JplMissionOption) -> list[EvidenceRecord]:
    """R48: the server served this exact option; its provenance is the server's own record."""
    traj = run.input_snapshot.trajectory
    pv = option.source
    out: list[EvidenceRecord] = []
    for name, unit in _TRAJECTORY_FIELDS:
        if getattr(traj, name) is None:
            continue
        informational = name == "mission_delta_v_km_per_s"
        out.append(
            EvidenceRecord(
                id=f"ev-trajectory-{name}",
                subject_id=f"trajectory.{name}",
                fidelity=pv.fidelity,
                source_title=pv.source_name,
                source_url=pv.source_url,
                source_version=pv.source_version,
                retrieved_at=pv.retrieved_at,
                unit=unit,
                conversion_notes="JPL km/s and km^2/s^2 kept as served; SI in the engine.",
                assumptions=[
                    f"Verified by this server: {traj.raw_source_ref} ({option.designation}).",
                    *(
                        [
                            "JPL total delta-v is informational; the spacecraft burn comes "
                            "from the scenario (R41)."
                        ]
                        if informational
                        else []
                    ),
                    *pv.assumptions,
                ],
                limitations=_limitations(
                    pv.fidelity,
                    pv.source_url,
                    *(["Unit km^2/s^2 (not an enumerated contract unit)."] if unit is None else []),
                ),
            )
        )
    return out


def _trajectory_records(
    run: MissionRun, verified: JplMissionOption | None = None
) -> list[EvidenceRecord]:
    """Client-supplied trajectory provenance is never trusted (R36). A JPL trajectory becomes
    source-backed only when the server verifies its reference and values (R48)."""
    if verified is not None:
        return _verified_records(run, verified) + _destination_records(run)
    snap = run.input_snapshot
    traj = snap.trajectory
    ref = traj.raw_source_ref
    claims_jpl = traj.provider == "jpl-mdesign"
    link = _jpl_link(ref) if claims_jpl else None
    if claims_jpl:
        title = "Claimed JPL SSD/CNEOS Mission Design API (unverified)"
    elif traj.provider == "scenario-preset":
        title = "MISSIONFORGE scenario preset (illustrative)"
    else:
        title = "Manual estimate entered by the player"
    out: list[EvidenceRecord] = []
    for name, unit in _TRAJECTORY_FIELDS:
        if getattr(traj, name) is None:
            continue
        extra: list[str] = [CLAIMED_JPL] if claims_jpl else []
        if unit is None:
            extra.append("Unit km^2/s^2 (not an enumerated contract unit).")
        out.append(
            EvidenceRecord(
                id=f"ev-trajectory-{name}",
                subject_id=f"trajectory.{name}",
                fidelity="gameplay-estimate",
                source_title=title,
                source_url=link,
                source_version=traj.option_id,
                unit=unit,
                assumptions=[
                    f"Trajectory provider: {traj.provider}.",
                    *(_client_claim_notes(ref, link) if claims_jpl else []),
                ],
                limitations=_limitations("gameplay-estimate", link, *extra),
            )
        )
    return out + _destination_records(run)


def _destination_records(run: MissionRun) -> list[EvidenceRecord]:
    snap = run.input_snapshot
    out: list[EvidenceRecord] = []
    dest = snap.destination.source
    if dest is not None:
        out.append(
            EvidenceRecord(
                id=f"ev-destination-{snap.destination.body_id}",
                subject_id=f"destination.{snap.destination.body_id}",
                fidelity="gameplay-estimate",
                source_title=dest.source_name,
                source_version=dest.source_version,
                assumptions=list(dest.assumptions),
                limitations=_limitations(
                    "gameplay-estimate",
                    None,
                    "Destination provenance comes from the run's own snapshot and is not verified.",
                ),
            )
        )
    return out


def _telemetry_records(run: MissionRun) -> list[EvidenceRecord]:
    lowest: dict[str, tuple[Fidelity, Unit]] = {}
    for t in run.telemetry:
        cur = lowest.get(t.channel)
        if cur is None or _FIDELITY_RANK[t.fidelity] < _FIDELITY_RANK[cur[0]]:
            lowest[t.channel] = (t.fidelity, t.unit)
    return [
        EvidenceRecord(
            id=f"ev-telemetry-{channel}",
            subject_id=f"telemetry.{channel}",
            fidelity=fid,
            source_title=ENGINE_SOURCE,
            source_version=run.engine_version,
            unit=unit,
            assumptions=["Sampled at phase, maneuver, observation and contact checkpoints."],
            limitations=_limitations(
                fid, None, "Reported fidelity is the lowest of the channel's samples."
            ),
        )
        for channel, (fid, unit) in sorted(lowest.items())
    ]


def _budget_records(analysis: MissionAnalysis) -> list[EvidenceRecord]:
    out: list[EvidenceRecord] = []
    for name in BUDGET_QUANTITIES:
        q = getattr(analysis.budgets, name)
        out.append(
            EvidenceRecord(
                id=f"ev-budget-{name.replace('_', '-')}",
                subject_id=f"budget.{name}",
                fidelity=q.provenance.fidelity,
                source_title=q.provenance.source_name,
                source_url=q.provenance.source_url if _is_http(q.provenance.source_url) else None,
                source_version=analysis.engine_version,
                unit=q.unit,
                conversion_notes=f"model {q.provenance.source_version}"
                if q.provenance.source_version
                else None,
                assumptions=list(q.provenance.assumptions),
                limitations=_limitations(q.provenance.fidelity, q.provenance.source_url),
                related_ids=[c.id for c in analysis.constraints if c.status != "pass"],
            )
        )
    out.append(
        EvidenceRecord(
            id="ev-budget-margins",
            subject_id="budget.margins",
            fidelity="derived",
            source_title=ENGINE_SOURCE,
            source_version=analysis.engine_version,
            unit="fraction",
            assumptions=list(analysis.assumptions),
            limitations=["Margins are computed from the budget quantities above."],
        )
    )
    return out


def build_evidence_records(
    run: MissionRun,
    catalog: Mapping[str, CatalogComponent],
    *,
    analysis: MissionAnalysis | None = None,
    verified_trajectory: JplMissionOption | None = None,
) -> list[EvidenceRecord]:
    """One record per catalogue parameter used, trajectory value, telemetry channel, derived
    budget (when `analysis` is given) and the run outcome. Nothing is invented: a value with
    no source link carries an explicit `unavailable-source` limitation, and a component the
    catalogue does not know is `not-modelled`."""
    out = _component_records(run, catalog, run.catalog_version)
    out += _trajectory_records(run, verified_trajectory)
    out += _telemetry_records(run)
    if analysis is not None:
        out += _budget_records(analysis)
    out.append(
        EvidenceRecord(
            id="ev-run-outcome",
            subject_id=f"run.{run.run_id}",
            fidelity="derived",
            source_title=ENGINE_SOURCE,
            source_version=run.engine_version,
            assumptions=[
                f"Seed {run.seed}; event set {run.scenario_event_set_id}.",
                f"Experimental what-if run: {'yes' if run.experimental else 'no'}.",
            ],
            limitations=list(run.final_report.limitations),
        )
    )
    return out


def export_mission_dossier(
    run: MissionRun,
    catalog: Mapping[str, CatalogComponent],
    *,
    exported_at: datetime,
    app_version: str,
    analysis: MissionAnalysis | None = None,
    replay: ReplayCheck | None = None,
    research: ResearchEvidence | None = None,
    verified_trajectory: JplMissionOption | None = None,
) -> Dossier:
    """Build the passport: a MissionPackage (JSON) and a self-contained HTML report."""
    records = build_evidence_records(
        run, catalog, analysis=analysis, verified_trajectory=verified_trajectory
    )
    package = MissionPackage(
        exported_at=exported_at,
        mission=run.input_snapshot,
        latest_analysis=analysis,
        runs=[run],
        evidence=records,
        manifest=MissionPackageManifest(
            app_version=app_version,
            engine_version=run.engine_version,
            catalog_version=run.catalog_version,
            scenario_version=run.manifest.scenario_version,
        ),
        research=research,
    )
    html = render_html(
        run, catalog, records, analysis, replay, exported_at, app_version, research=research
    )
    return Dossier(package=package, html=html)
