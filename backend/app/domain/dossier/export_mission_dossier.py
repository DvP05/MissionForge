# ruff: noqa: E501  (HTML template strings)
"""Evidence Passport v1: evidence ledger plus the exportable JSON package and HTML report.

Pure (architecture 19.9, M18, prod 21.4): the export time, app version, analysis and replay
check are passed in. Every string that reaches the HTML is escaped; the page is one
self-contained document (inline CSS with a print stylesheet, no scripts, no external files).
The output is deterministic: the same inputs give byte-identical JSON and HTML.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from html import escape

from app.domain.dossier.build_run_manifest import build_run_manifest
from app.schemas.analysis import MissionAnalysis
from app.schemas.catalog import CatalogComponent
from app.schemas.evidence import EvidenceRecord, MissionPackage, MissionPackageManifest
from app.schemas.simulation import MissionEvent, MissionRun
from app.schemas.units import Fidelity, Provenance, Unit

NON_ENDORSEMENT = "Independent educational prototype; not a NASA/JPL product or endorsement."
UNAVAILABLE_NO_AUDIT = "unavailable-source: no primary source audited yet"
ENGINE_SOURCE = "MISSIONFORGE simulation engine"
BUDGET_QUANTITIES = (
    "dry_mass_kg", "propellant_mass_kg", "wet_mass_kg", "average_power_w", "peak_power_w",
    "data_generated_bits", "data_downlinked_bits", "required_delta_v_km_per_s",
    "available_delta_v_km_per_s", "estimated_cost_usd",
)  # fmt: skip
_FIDELITY_RANK: dict[str, int] = {
    "not-modelled": 0,
    "gameplay-estimate": 1,
    "derived": 2,
    "source-backed": 3,
}


@dataclass(frozen=True)
class ReplayCheck:
    """Result of the server-side replay check at export time (never a client claim)."""

    status: str  # "identical-replay" | "version-mismatch" | "diverged"
    mismatches: tuple[str, ...]


@dataclass(frozen=True)
class Dossier:
    package: MissionPackage
    html: str


# ---- Evidence ledger ----------------------------------------------------------------------


def _limitations(fidelity: Fidelity, url: str | None, *extra: str) -> list[str]:
    out: list[str] = []
    if fidelity != "derived" and not url:
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
        source_url=pv.source_url,
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


def _trajectory_records(run: MissionRun) -> list[EvidenceRecord]:
    snap = run.input_snapshot
    traj = snap.trajectory
    ref = traj.raw_source_ref
    url = ref if ref and ref.startswith(("https://", "http://")) else None
    jpl_backed = traj.provider == "jpl-mdesign" and url is not None
    fidelity: Fidelity = "source-backed" if jpl_backed else "gameplay-estimate"
    if traj.provider == "jpl-mdesign":
        title = "JPL SSD/CNEOS Mission Design API"
    elif traj.provider == "scenario-preset":
        title = "MISSIONFORGE scenario preset (illustrative)"
    else:
        title = "Manual estimate entered by the player"
    out: list[EvidenceRecord] = []
    for name, unit in _TRAJECTORY_FIELDS:
        if getattr(traj, name) is None:
            continue
        extra: list[str] = []
        if traj.provider == "jpl-mdesign" and not jpl_backed:
            extra.append("Labelled JPL but no source reference was recorded; not source-backed.")
        if unit is None:
            extra.append("Unit km^2/s^2 (not an enumerated contract unit).")
        out.append(
            EvidenceRecord(
                id=f"ev-trajectory-{name}",
                subject_id=f"trajectory.{name}",
                fidelity=fidelity,
                source_title=title,
                source_url=url if jpl_backed else None,
                source_version=traj.option_id,
                unit=unit,
                assumptions=[f"Trajectory provider: {traj.provider}."],
                limitations=_limitations(fidelity, url if jpl_backed else None, *extra),
            )
        )
    dest = snap.destination.source
    if dest is not None:
        out.append(
            _from_provenance(
                f"ev-destination-{snap.destination.body_id}",
                f"destination.{snap.destination.body_id}",
                dest,
                None,
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


def _budget_records(run: MissionRun, analysis: MissionAnalysis) -> list[EvidenceRecord]:
    out: list[EvidenceRecord] = []
    for name in BUDGET_QUANTITIES:
        q = getattr(analysis.budgets, name)
        out.append(
            EvidenceRecord(
                id=f"ev-budget-{name.replace('_', '-')}",
                subject_id=f"budget.{name}",
                fidelity=q.provenance.fidelity,
                source_title=q.provenance.source_name,
                source_url=q.provenance.source_url,
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
) -> list[EvidenceRecord]:
    """One record per catalogue parameter used, trajectory value, telemetry channel, derived
    budget (when `analysis` is given) and the run outcome. Nothing is invented: a value with
    no source link carries an explicit `unavailable-source` limitation, and a component the
    catalogue does not know is `not-modelled`."""
    out = _component_records(run, catalog, run.catalog_version)
    out += _trajectory_records(run)
    out += _telemetry_records(run)
    if analysis is not None:
        out += _budget_records(run, analysis)
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


# ---- HTML ----------------------------------------------------------------------------------

_CSS = """
:root{color-scheme:light;--ink:#14202b;--muted:#51606e;--line:#c9d2db;--bg:#fff;--soft:#f2f5f8}
*{box-sizing:border-box}
body{margin:0;padding:24px 16px;background:var(--bg);color:var(--ink);
font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:960px;margin:0 auto}
h1{font-size:26px;margin:0 0 4px}h2{font-size:19px;margin:28px 0 8px;border-bottom:1px solid var(--line);
padding-bottom:4px}h3{font-size:15px;margin:16px 0 6px}
p,li{overflow-wrap:anywhere}.muted{color:var(--muted)}.mono{font-family:ui-monospace,Consolas,monospace;font-size:12px}
.outcome{font-size:22px;font-weight:700;margin:6px 0}.banner{border:1px solid var(--line);
background:var(--soft);padding:8px 12px;border-radius:6px;margin:8px 0}
table{border-collapse:collapse;width:100%;font-size:13px;margin:6px 0}
th,td{border:1px solid var(--line);padding:4px 8px;text-align:left;vertical-align:top;overflow-wrap:anywhere}
th{background:var(--soft)}.table-wrap{overflow-x:auto}
dl{display:grid;grid-template-columns:max-content 1fr;gap:2px 16px;margin:6px 0}dt{color:var(--muted)}dd{margin:0}
footer{margin-top:32px;border-top:1px solid var(--line);padding-top:12px;font-size:13px}
@media print{body{padding:0;font-size:11pt}.table-wrap{overflow:visible}
h2{break-after:avoid}table,.banner{break-inside:avoid}a{color:inherit;text-decoration:none}}
"""

_OUTCOME_LABEL = {
    "success": "Mission success",
    "partial": "Partial success",
    "failure": "Mission failure",
    "terminated": "Mission terminated early",
}


def _e(value: object) -> str:
    return escape(str(value), quote=True)


def _num(v: float) -> str:
    s = f"{v:,.3f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def _pct(v: float) -> str:
    return f"{v * 100:.1f}%"


def _ts(d: datetime) -> str:
    return d.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _table(headers: list[str], rows: list[list[str]]) -> str:
    """Cells are already escaped by the caller."""
    head = "".join(f"<th>{_e(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def _ul(items: list[str] | tuple[str, ...], none: str) -> str:
    if not items:
        return f'<p class="muted">{_e(none)}</p>'
    return "<ul>" + "".join(f"<li>{_e(i)}</li>" for i in items) + "</ul>"


def _section(title: str, body: str) -> str:
    return f"<section><h2>{_e(title)}</h2>{body}</section>"


def _summary(run: MissionRun, analysis: MissionAnalysis | None) -> str:
    rep = run.final_report
    achieved = sum(o.status == "achieved" for o in run.science_outcomes)
    total = len(run.science_outcomes)
    sentence = {
        "success": f"All science objectives were achieved in this simulated run ({achieved} of {total}).",
        "partial": f"Some, but not all, objectives were achieved in this simulated run ({achieved} of {total}).",
        "failure": f"The simulated flight did not achieve its objectives ({achieved} of {total} achieved).",
        "terminated": "The simulated mission ended before it completed operations; see root causes below.",
    }[rep.outcome]
    parts = [
        f'<p class="outcome">{_e(_OUTCOME_LABEL[rep.outcome])}</p>',
        f"<p>{_e(sentence)}</p>",
        f"<p>{_e(rep.summary)}</p>",
        f"<p>Total score {_e(_num(rep.score.total))} of 100.</p>",
    ]
    if run.experimental:
        parts.append(
            '<p class="banner">Experimental what-if run: the design failed a hard gate and was '
            "flown anyway; it is not a mission-ready design.</p>"
        )
    unmodelled = (
        [c.id for c in analysis.constraints if c.status == "not-modelled"] if analysis else []
    )
    if analysis is None:
        completeness = (
            "Model completeness: the design analysis was not available for this export, so "
            "which checks are not modelled cannot be listed."
        )
    elif unmodelled:
        completeness = (
            f"Model completeness: {len(unmodelled)} check(s) are not modelled "
            f"({', '.join(unmodelled)}). A check this model does not cover is a gap in the "
            "model, not a mission failure."
        )
    else:
        completeness = (
            "Model completeness: no constraint is flagged not-modelled. Outcome describes the "
            "simulated flight only."
        )
    parts.append(f"<p>{_e(completeness)}</p>")
    return _section("Executive summary", "".join(parts))


def _brief(run: MissionRun, catalog: Mapping[str, CatalogComponent]) -> str:
    s = run.input_snapshot
    t = s.trajectory
    c = s.constraints
    ops = s.operations
    dl = (
        f"<dl><dt>Title</dt><dd>{_e(s.title)}</dd><dt>Mission id</dt><dd>{_e(s.mission_id)}</dd>"
        f"<dt>Scenario</dt><dd>{_e(s.scenario_id)}</dd>"
        f"<dt>Design revision</dt><dd>{_e(s.design_revision)}</dd>"
        f"<dt>Destination</dt><dd>{_e(s.destination.name)} ({_e(s.destination.body_type)})</dd>"
        f"<dt>Trajectory</dt><dd>{_e(t.provider)} / {_e(t.option_id)}, departure {_e(t.departure_date)}"
        f"{', arrival ' + _e(t.arrival_date) if t.arrival_date else ''}"
        f"{', time of flight ' + _e(_num(t.time_of_flight_days)) + ' d' if t.time_of_flight_days is not None else ''}</dd>"
        f"<dt>Operations</dt><dd>{_e(_num(ops.mission_duration_days))} d, safe mode {_e(ops.safe_mode_policy)}, "
        f"autonomy {_e(ops.autonomy_level)}</dd>"
        f"<dt>Budget limit</dt><dd>{_e(_num(c.maximum_budget_usd))} USD (gameplay estimate)</dd></dl>"
    )
    instruments = [catalog.get(i) for i in s.architecture.instrument_ids]
    rows: list[list[str]] = []
    for obj in s.science_objectives:
        for m in obj.required_measurements:
            providers = [
                i.name
                for i in instruments
                if i is not None and m.instrument_capability in i.capabilities
            ]
            rows.append(
                [
                    _e(obj.title),
                    f"{_e(m.id)}: {_e(m.description)}",
                    _e(m.instrument_capability),
                    _e(_num(m.coverage_weight)),
                    "yes" if m.required else "no",
                    _e(", ".join(providers)) if providers else "none selected",
                ]
            )
    questions = "".join(
        f"<li><strong>{_e(o.title)}</strong> (priority {_e(_num(o.priority))}): {_e(o.question)}</li>"
        for o in s.science_objectives
    )
    trace = _table(
        [
            "Objective",
            "Measurement",
            "Capability",
            "Weight",
            "Required",
            "Instruments providing it",
        ],
        rows,
    )
    return _section(
        "Mission brief",
        f"{dl}<h3>Science objectives</h3><ul>{questions}</ul>"
        f"<h3>Objective to measurement to instrument traceability</h3>{trace}",
    )


def _param(comp: CatalogComponent, *names: str) -> tuple[str, Fidelity | None]:
    for n in names:
        q = comp.parameters.get(n)
        if q is not None:
            return _num(q.value), q.provenance.fidelity
    return "-", None


def _architecture(run: MissionRun, catalog: Mapping[str, CatalogComponent]) -> str:
    a = run.input_snapshot.architecture
    entries: list[tuple[str, str]] = [
        ("launch", a.launch_vehicle_id), ("bus", a.bus_id), ("propulsion", a.propulsion_id),
        ("power", a.power_id), ("adcs", a.adcs_id), ("communications", a.communications_id),
        ("thermal", a.thermal_id), ("cdh", a.cdh_id),
        *(("instrument", i) for i in a.instrument_ids), ("ground", a.ground_segment_id),
    ]  # fmt: skip
    rows: list[list[str]] = []
    for cat, cid in entries:
        comp = catalog.get(cid)
        if comp is None:
            rows.append([_e(cat), _e(cid), "-", "-", "-", "not-modelled (not in this catalogue)"])
            continue
        mass, f1 = _param(comp, "mass", "dry_mass")
        power, f2 = _param(comp, "power_w")
        cost, f3 = _param(comp, "cost")
        fids = sorted({f for f in (f1, f2, f3) if f}, key=str)
        label = ", ".join(fids) + (" (illustrative)" if comp.is_illustrative else "")
        rows.append(
            [
                _e(cat),
                f"{_e(comp.name)} <span class='mono'>{_e(cid)}</span>",
                mass,
                power,
                cost,
                _e(label),
            ]
        )
    table = _table(
        ["Category", "Component", "Mass (kg)", "Power (W)", "Cost (USD)", "Fidelity"], rows
    )
    note = "Mass, power and cost are catalogue values (gameplay estimates); launch vehicles list a mass limit, not a mass."
    return _section("Selected architecture", f"{table}<p class='muted'>{_e(note)}</p>")


def _budgets(run: MissionRun, analysis: MissionAnalysis | None) -> str:
    if analysis is None:
        return _section(
            "Budgets and margins",
            "<p>Budgets were not available for this export: this server could not re-analyse "
            "the design with its catalogue. No values are shown rather than guessed.</p>",
        )
    b = analysis.budgets
    rows = []
    for name in BUDGET_QUANTITIES:
        q = getattr(b, name)
        rows.append([_e(name), _e(_num(q.value)), _e(q.unit), _e(q.provenance.fidelity)])
    margins = [
        ["mass margin", _pct(b.mass_margin_fraction)],
        ["energy margin", _pct(b.energy_margin_fraction)],
        ["data margin", _pct(b.data_margin_fraction)],
        ["delta-v margin", f"{_num(b.delta_v_margin_km_per_s)} km/s"],
    ]
    cons = [[_e(c.id), _e(c.status), _e(c.explanation)] for c in analysis.constraints]
    notice = ""
    if (
        analysis.engine_version != run.engine_version
        or analysis.catalog_version != run.catalog_version
    ):
        notice = (
            f"<p class='banner'>These budgets were recomputed by engine {_e(analysis.engine_version)} / "
            f"catalogue {_e(analysis.catalog_version)}; the run was recorded with engine "
            f"{_e(run.engine_version)} / catalogue {_e(run.catalog_version)}.</p>"
        )
    return _section(
        "Budgets and margins",
        f"{notice}{_table(['Quantity', 'Value', 'Unit', 'Fidelity'], rows)}"
        f"{_table(['Margin', 'Value'], [[_e(a), _e(v)] for a, v in margins])}"
        f"<p>Feasibility: {_e(analysis.feasibility)}; mission ready: {'yes' if analysis.mission_ready else 'no'}.</p>"
        f"<h3>Constraints</h3>{_table(['Constraint', 'Status', 'Explanation'], cons)}",
    )


def _decision_line(run: MissionRun, ev: MissionEvent) -> str:
    out = ""
    for d in run.decisions:
        if d.event_id != ev.id:
            continue
        choice = next((c for c in ev.choices if c.id == d.choice_id), None)
        label = choice.label if choice else d.choice_id
        out += (
            f"<br><em>Decision:</em> {_e(label)} "
            f"(decision_maker: {_e(d.decision_maker)}; {_e(d.rationale)})"
        )
    return out


def _timeline(run: MissionRun) -> str:
    items: list[tuple[float, int, str]] = []
    for t in run.phase_transitions:
        items.append((t.mission_day, -1, f"<strong>Phase: {_e(t.phase)}</strong>"))
    for ev in run.events:
        if ev.type == "telemetry":
            continue
        who = f", decision_maker: {_e(ev.decision_maker)}" if ev.decision_maker else ""
        items.append(
            (
                ev.mission_day,
                ev.sequence,
                f"[{_e(ev.type)}, {_e(ev.severity)}{who}] {_e(ev.title)}: {_e(ev.description)}"
                f"{_decision_line(run, ev)}",
            )
        )
    items.sort(key=lambda x: (x[0], x[1]))
    lis = "".join(f"<li>Day {_e(_num(d))}: {text}</li>" for d, _, text in items)
    return _section("Operations timeline", f"<ol>{lis}</ol>")


def _anomalies(run: MissionRun) -> str:
    rep = run.final_report
    rows = [
        [
            _e(_num(e.mission_day)),
            _e(e.severity),
            _e(e.title),
            _e(e.description),
            _e(e.decision_maker or "-"),
        ]
        for e in run.events
        if e.type == "anomaly"
    ]
    table = (
        _table(["Day", "Severity", "Event", "Description", "Resolved by"], rows)
        if rows
        else "<p class='muted'>No anomaly events occurred in this run.</p>"
    )
    return _section(
        "Anomalies and realized risks",
        f"{table}<h3>Realized risks</h3>{_ul(rep.realized_risks, 'No risks were realized.')}"
        f"<h3>Root causes</h3>{_ul(rep.root_causes, 'No root causes were recorded.')}"
        f"<h3>Counterfactuals</h3>{_ul(rep.counterfactuals, 'No counterfactual was computed.')}",
    )


def _science(run: MissionRun) -> str:
    titles = {o.id: o.title for o in run.input_snapshot.science_objectives}
    rows = [
        [
            _e(titles.get(o.objective_id, o.objective_id)),
            _e(o.status),
            _pct(o.collected_fraction),
            _pct(o.returned_fraction),
        ]
        for o in run.science_outcomes
    ]
    table = (
        _table(["Objective", "Status", "Collected", "Returned to Earth"], rows)
        if rows
        else ("<p class='muted'>No objective outcomes were produced.</p>")
    )
    return _section(
        "Science collected and returned",
        "<p class='muted'>Collected data is not the same as data returned to Earth; only "
        f"returned data counts toward an objective.</p>{table}",
    )


def _score(run: MissionRun) -> str:
    sc = run.final_report.score
    rows = [
        [_e(d.id), _e(_num(d.weight)), _e(_num(d.score)), _e(d.explanation)] for d in sc.dimensions
    ]
    return _section(
        "Score breakdown",
        f"<p>Total {_e(_num(sc.total))} of 100 (weighted sum of the five dimensions).</p>"
        + _table(["Dimension", "Weight", "Score (of 100)", "Explanation"], rows),
    )


def _replay_text(replay: ReplayCheck | None) -> str:
    if replay is None:
        return (
            "Replay was not verified at export time; do not treat this run as an identical "
            "replay until it is re-run and compared."
        )
    if replay.status == "identical-replay":
        return (
            "Replay verified at export: re-running the recorded inputs reproduced this run "
            "(identical replay)."
        )
    diffs = ", ".join(replay.mismatches) or "none listed"
    return (
        f"Replay check at export: this is not an identical replay (status {replay.status}; "
        f"differences: {diffs})."
    )


def _manifest(
    run: MissionRun, app_version: str, exported_at: datetime, replay: ReplayCheck | None
) -> str:
    m = build_run_manifest(run, app_version=app_version)
    rows = [
        ("schemaVersion", m.schema_version), ("engineVersion", m.engine_version),
        ("catalogVersion", m.catalog_version), ("scenarioVersion", m.scenario_version),
        ("eventSetId", m.event_set_id), ("seed", m.seed),
        ("appVersion (exporting app)", m.app_version),
        ("appVersion (recorded with run)", run.manifest.app_version),
        ("runId", run.run_id), ("designRevision", run.design_revision),
        ("experimental", "yes" if run.experimental else "no"), ("exportedAt", _ts(exported_at)),
    ]  # fmt: skip
    dl = (
        "<dl>"
        + "".join(f"<dt>{_e(k)}</dt><dd class='mono'>{_e(v)}</dd>" for k, v in rows)
        + "</dl>"
    )
    return _section("Run manifest", f"{dl}<p>{_e(_replay_text(replay))}</p>")


def _ledger(records: list[EvidenceRecord], analysis: MissionAnalysis | None) -> str:
    rows: list[list[str]] = []
    for r in records:
        if r.source_url and r.source_url.startswith(("https://", "http://")):
            link = f'<a href="{_e(r.source_url)}" rel="noopener noreferrer">{_e(r.source_url)}</a>'
        elif r.source_url:
            link = _e(r.source_url)
        else:
            link = _e(
                next(
                    (x for x in r.limitations if x.startswith("unavailable-source")),
                    "not applicable (derived by the engine)",
                )
            )
        source = _e(r.source_title or "-") + (
            f" ({_e(r.source_version)})" if r.source_version else ""
        )
        rows.append(
            [
                f"<span class='mono'>{_e(r.id)}</span>",
                _e(r.subject_id),
                _e(r.fidelity),
                source,
                link,
                _e(r.unit or "-"),
                _e("; ".join(r.assumptions) or "-"),
                _e("; ".join(r.limitations) or "-"),
            ]
        )
    table = _table(
        ["Id", "Subject", "Fidelity", "Source", "Link", "Unit", "Assumptions", "Limitations"], rows
    )
    extra = _ul(analysis.assumptions if analysis else [], "No analysis assumptions are listed.")
    return _section(
        "Sources and assumptions",
        f"<p>Every value used is listed. No catalogue value is source-backed in this version.</p>{table}"
        f"<h3>Analysis assumptions</h3>{extra}",
    )


def _limitations_section(run: MissionRun) -> str:
    fixed = [
        "All catalogue values are illustrative gameplay estimates (R3), not NASA, JPL or vendor data.",
        "The simulation is a deterministic event model, not orbital propagation or a flight-software test.",
        "This passport is an educational record of a game run; it must not be used for real mission planning.",
        NON_ENDORSEMENT,
    ]
    return _section(
        "Limitations",
        f"<h3>This run</h3>{_ul(run.final_report.limitations, 'No run limitations were reported.')}"
        f"<h3>This passport</h3>{_ul(fixed, '')}",
    )


def _render_html(
    run: MissionRun,
    catalog: Mapping[str, CatalogComponent],
    records: list[EvidenceRecord],
    analysis: MissionAnalysis | None,
    replay: ReplayCheck | None,
    exported_at: datetime,
    app_version: str,
) -> str:
    title = run.input_snapshot.title
    body = "".join(
        [
            _summary(run, analysis),
            _brief(run, catalog),
            _architecture(run, catalog),
            _budgets(run, analysis),
            _timeline(run),
            _anomalies(run),
            _science(run),
            _score(run),
            _manifest(run, app_version, exported_at, replay),
            _ledger(records, analysis),
            _limitations_section(run),
        ]
    )
    return (
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>MISSIONFORGE Evidence Passport: {_e(title)}</title><style>{_CSS}</style></head>"
        f"<body><main><header><h1>Evidence Passport: {_e(title)}</h1>"
        f'<p class="muted">Run <span class="mono">{_e(run.run_id)}</span> · exported {_e(_ts(exported_at))}</p>'
        f'<p class="banner">{_e(NON_ENDORSEMENT)}</p></header>{body}'
        f"<footer>{_e(NON_ENDORSEMENT)}</footer></main></body></html>\n"
    )


def export_mission_dossier(
    run: MissionRun,
    catalog: Mapping[str, CatalogComponent],
    *,
    exported_at: datetime,
    app_version: str,
    analysis: MissionAnalysis | None = None,
    replay: ReplayCheck | None = None,
) -> Dossier:
    """Build the passport: a MissionPackage (JSON) and a self-contained HTML report."""
    records = build_evidence_records(run, catalog, analysis=analysis)
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
    )
    html = _render_html(run, catalog, records, analysis, replay, exported_at, app_version)
    return Dossier(package=package, html=html)
