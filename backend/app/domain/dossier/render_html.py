"""Self-contained HTML renderer for the Evidence Passport (architecture 19.9).

Every dynamic string goes through `_e` (html.escape). One document: inline CSS with a print
stylesheet, no scripts, no external files. Deterministic for the same inputs.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from html import escape

from app.domain.dossier.build_run_manifest import build_run_manifest
from app.schemas.analysis import MissionAnalysis
from app.schemas.catalog import CatalogComponent
from app.schemas.evidence import EvidenceRecord, ResearchEvidence
from app.schemas.simulation import MissionEvent, MissionRun
from app.schemas.units import Fidelity

NON_ENDORSEMENT = "Independent educational prototype; not a NASA/JPL product or endorsement."
BUDGET_QUANTITIES = (
    "dry_mass_kg", "propellant_mass_kg", "wet_mass_kg", "average_power_w", "peak_power_w",
    "data_generated_bits", "data_downlinked_bits", "required_delta_v_km_per_s",
    "available_delta_v_km_per_s", "estimated_cost_usd",
)  # fmt: skip


@dataclass(frozen=True)
class ReplayCheck:
    """Result of the server-side replay check at export time (never a client claim)."""

    status: str  # "identical-replay" | "version-mismatch" | "diverged"
    mismatches: tuple[str, ...]


_CSS = """
:root{color-scheme:light;--ink:#14202b;--muted:#51606e;--line:#c9d2db;--bg:#fff;--soft:#f2f5f8}
*{box-sizing:border-box}
body{margin:0;padding:24px 16px;background:var(--bg);color:var(--ink);
font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:960px;margin:0 auto}
h1{font-size:26px;margin:0 0 4px}
h2{font-size:19px;margin:28px 0 8px;border-bottom:1px solid var(--line);
padding-bottom:4px}
h3{font-size:15px;margin:16px 0 6px}
p,li{overflow-wrap:anywhere}
.muted{color:var(--muted)}
.mono{font-family:ui-monospace,Consolas,monospace;font-size:12px}
.outcome{font-size:22px;font-weight:700;margin:6px 0}
.banner{border:1px solid var(--line);
background:var(--soft);padding:8px 12px;border-radius:6px;margin:8px 0}
table{border-collapse:collapse;width:100%;font-size:13px;margin:6px 0}
th,td{border:1px solid var(--line);padding:4px 8px;text-align:left;
vertical-align:top;overflow-wrap:anywhere}
th{background:var(--soft)}
.table-wrap{overflow-x:auto}
dl{display:grid;grid-template-columns:max-content 1fr;gap:2px 16px;margin:6px 0}
dt{color:var(--muted)}
dd{margin:0}
footer{margin-top:32px;border-top:1px solid var(--line);padding-top:12px;font-size:13px}
@media print{body{padding:0;font-size:11pt}
.table-wrap{overflow:visible}
h2{break-after:avoid}
table,.banner{break-inside:avoid}
.unverified{border:2px solid #9a3412;background:#fff7ed;color:#7c2d12;font-weight:600}
a{color:inherit;text-decoration:none}}
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
    return f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'  # noqa: E501


def _ul(items: list[str] | tuple[str, ...], none: str) -> str:
    if not items:
        return f'<p class="muted">{_e(none)}</p>'
    return "<ul>" + "".join(f"<li>{_e(i)}</li>" for i in items) + "</ul>"


def _section(title: str, body: str) -> str:
    return f"<section><h2>{_e(title)}</h2>{body}</section>"


def _unverified_text(replay: ReplayCheck | None) -> str | None:
    """R39: the up-front warning for any passport that is not a verified identical replay."""
    if replay is not None and replay.status == "identical-replay":
        return None
    if replay is None:
        why = "the replay was not checked at export time"
    elif replay.status == "version-mismatch":
        why = "engine, catalogue or scenario versions differ from the recorded run"
    else:
        why = "re-running the recorded inputs did not reproduce this run"
    return (
        f"Unverified: {why}. Treat the results below as a record of a claimed run, "
        "not a verified reproducible result."
    )


def _summary(
    run: MissionRun, analysis: MissionAnalysis | None, replay: ReplayCheck | None = None
) -> str:
    rep = run.final_report
    achieved = sum(o.status == "achieved" for o in run.science_outcomes)
    total = len(run.science_outcomes)
    sentence = {
        "success": f"All science objectives were achieved in this simulated run ({achieved} of {total}).",  # noqa: E501
        "partial": f"Some, but not all, objectives were achieved in this simulated run ({achieved} of {total}).",  # noqa: E501
        "failure": f"The simulated flight did not achieve its objectives ({achieved} of {total} achieved).",  # noqa: E501
        "terminated": "The simulated mission ended before it completed operations; see root causes below.",  # noqa: E501
    }[rep.outcome]
    unverified = _unverified_text(replay)
    parts = [
        *([f'<p class="banner unverified">{_e(unverified)}</p>'] if unverified else []),
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
        f"<dt>Trajectory</dt><dd>{_e(t.provider)} / {_e(t.option_id)}, departure {_e(t.departure_date)}"  # noqa: E501
        f"{', arrival ' + _e(t.arrival_date) if t.arrival_date else ''}"
        f"{', time of flight ' + _e(_num(t.time_of_flight_days)) + ' d' if t.time_of_flight_days is not None else ''}</dd>"  # noqa: E501
        f"<dt>Operations</dt><dd>{_e(_num(ops.mission_duration_days))} d, safe mode {_e(ops.safe_mode_policy)}, "  # noqa: E501
        f"autonomy {_e(ops.autonomy_level)}</dd>"
        f"<dt>Budget limit</dt><dd>{_e(_num(c.maximum_budget_usd))} USD (gameplay estimate)</dd></dl>"  # noqa: E501
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
        f"<li><strong>{_e(o.title)}</strong> (priority {_e(_num(o.priority))}): {_e(o.question)}</li>"  # noqa: E501
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
    note = "Mass, power and cost are catalogue values (gameplay estimates); launch vehicles list a mass limit, not a mass."  # noqa: E501
    return _section("Selected architecture", f"{table}<p class='muted'>{_e(note)}</p>")


def _margin(
    value: float | None,
    fmt: Callable[[float], str],
    analysis: MissionAnalysis,
    constraint_id: str,
) -> str:
    """A margin value, or "—" plus why it is undefined (R38: never a fake 0)."""
    if value is not None:
        return fmt(value)
    c = next((x for x in analysis.constraints if x.id == constraint_id), None)
    reason = c.explanation if c is not None else "the analysis did not produce this margin"
    return f"— (not defined: {reason})"


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
        ["mass margin", _margin(b.mass_margin_fraction, _pct, analysis, "mass-launch-limit")],
        ["energy margin", _margin(b.energy_margin_fraction, _pct, analysis, "energy-closure")],
        ["data margin", _margin(b.data_margin_fraction, _pct, analysis, "data-return")],
        [
            "delta-v margin",
            _margin(
                b.delta_v_margin_km_per_s, lambda v: f"{_num(v)} km/s", analysis, "delta-v-margin"
            ),
        ],
    ]
    cons = [[_e(c.id), _e(c.status), _e(c.explanation)] for c in analysis.constraints]
    notice = ""
    if (
        analysis.engine_version != run.engine_version
        or analysis.catalog_version != run.catalog_version
    ):
        notice = (
            f"<p class='banner'>These budgets were recomputed by engine {_e(analysis.engine_version)} / "  # noqa: E501
            f"catalogue {_e(analysis.catalog_version)}; the run was recorded with engine "
            f"{_e(run.engine_version)} / catalogue {_e(run.catalog_version)}.</p>"
        )
    notice += (
        f"<p class='muted'>Budgets were recomputed at export by engine {_e(analysis.engine_version)} "  # noqa: E501
        f"(catalogue {_e(analysis.catalog_version)}) from the run's input snapshot.</p>"
    )
    return _section(
        "Budgets and margins",
        f"{notice}{_table(['Quantity', 'Value', 'Unit', 'Fidelity'], rows)}"
        f"{_table(['Margin', 'Value'], [[_e(a), _e(v)] for a, v in margins])}"
        f"<p>Feasibility: {_e(analysis.feasibility)}; mission ready: {'yes' if analysis.mission_ready else 'no'}.</p>"  # noqa: E501
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
    n_backed = sum(r.fidelity == "source-backed" for r in records)
    backed = (
        f"{n_backed} of {len(records)} records are source-backed."
        if n_backed
        else "No value in this passport is source-backed."
    )
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
        f"<p>Every value used is listed. {_e(backed)}</p>{table}"
        f"<h3>Analysis assumptions</h3>{extra}",
    )


_RESEARCH_NOTE = (
    "Recomputed at export by the current engine from this run's recorded design "
    "(seed = mission seed). Gameplay-level research aids, not flight analyses."
)


def _traceability(research: ResearchEvidence) -> str:
    stm = _table(
        ["Objective", "Requirement", "Required", "Instruments", "Observations", "Status"],
        [
            [
                _e(r.objective_title),
                _e(r.requirement_description),
                "yes" if r.required else "no",
                _e(", ".join(r.instrument_ids) or "none"),
                _e(r.observation_count),
                _e(r.status),
            ]
            for r in research.science_traceability
        ],
    )
    mtm = _table(
        ["Instrument", "Requirements", "Subsystems", "Observations"],
        [
            [
                _e(r.instrument_name),
                _e(", ".join(r.requirement_ids) or "none"),
                _e(", ".join(r.subsystem_ids) or "none"),
                _e(r.observation_count),
            ]
            for r in research.mission_traceability
        ],
    )
    if not research.science_traceability:
        stm = '<p class="muted">No science traceability rows were computed.</p>'
    if not research.mission_traceability:
        mtm = '<p class="muted">No mission traceability rows were computed.</p>'
    return _section(
        "Traceability matrices",
        f'<p class="muted">{_e(_RESEARCH_NOTE)}</p>'
        f"<h3>Science traceability (STM)</h3>{stm}"
        f"<h3>Mission traceability (MTM)</h3>{mtm}",
    )


def _pareto(research: ResearchEvidence) -> str:
    p = research.pareto
    if p is None:
        return _section("Design-space position", '<p class="muted">Not computed.</p>')
    if p.baseline_on_front:
        where = "The flown design is on the Pareto front (no sampled design beats it on every objective)."  # noqa: E501
    elif p.dominated_by:
        where = (
            f"The flown design is dominated by {len(p.dominated_by)} front design(s) "
            f"(e.g. {', '.join(p.dominated_by)})."
        )
    else:
        where = "The flown design is not on the Pareto front."
    arch = ", ".join(f"{k}: {v}" for k, v in sorted(p.archetypes.items())) or "none"
    dl = (
        f"<p>{_e(where)}</p>"
        f"<p>Seed {_e(p.seed)}; {_e(p.candidates_evaluated)} candidates evaluated; front size "
        f'{_e(p.front_size)}; flown design id <span class="mono">{_e(p.baseline_id)}</span>'
        f" ({'feasible' if p.baseline_feasible else 'infeasible'}).</p>"
        f"<p>Archetypes: {_e(arch)}.</p>"
    )
    return _section("Design-space position", dl + _ul(p.notes, ""))


def _robustness(research: ResearchEvidence) -> str:
    r = research.robustness
    if r is None:
        return _section("Robustness", '<p class="muted">Not computed.</p>')
    lo, hi = r.feasibility_wilson_95
    rows = []
    for name, q in r.metrics.items():

        def cell(v: float | None, unit: str = q.unit) -> str:
            if v is None:
                return "— (not defined)"
            return _e(_pct(v) if unit == "fraction" else f"{_num(v)} {unit}")

        rows.append([_e(name), cell(q.p10), cell(q.median), cell(q.p90), _e(q.defined_samples)])
    failures = [f"{cid}: {n} of {r.samples} samples" for cid, n in r.failure_counts.items()]
    body = (
        f"<p>Feasible in {_e(_pct(r.probability_feasible))} of {_e(r.samples)} samples "
        f"(Wilson 95% interval {_e(_pct(lo))}–{_e(_pct(hi))}); seed {_e(r.seed)}; profile "
        f"{_e(r.profile_version)}.</p>"
        f'<p class="muted">{_e(r.disclaimer)}</p>'
        + _table(["Metric", "p10", "Median", "p90", "Samples defined"], rows)
        + "<h3>Hard-constraint failures</h3>"
        + _ul(failures, "No hard constraint failed in any sample.")
        + "<h3>Assumptions</h3>"
        + _ul(r.assumptions, "")
    )
    return _section("Robustness", body)


def _schedule(research: ResearchEvidence) -> str:
    s = research.schedule
    if s is None:
        return _section("Science and downlink schedule", '<p class="muted">Not computed.</p>')
    cycles = _table(
        ["Cycle", "Observations", "Contact", "Buffer before", "Buffer after"],
        [
            [
                _e(c.id),
                _e(", ".join(c.observations) or "none"),
                _e(c.contact_window_id or "none"),
                _e(f"{_num(c.buffer_before_bits / 1e9)} Gbit"),
                _e(f"{_num(c.buffer_after_bits / 1e9)} Gbit"),
            ]
            for c in s.cycles
        ],
    )
    rejected = [f"{r.id}: {r.reason_code}" for r in s.rejected]
    return _section(
        "Science and downlink schedule",
        '<p class="muted">Greedy heuristic schedule, not an optimal plan.</p>'
        f"<p>{_e(len(s.accepted))} observation(s) accepted, {_e(len(s.rejected))} rejected; "
        f"data lost {_e(_num(s.data_lost_bits / 1e9))} Gbit.</p>"
        + cycles
        + "<h3>Rejected observations</h3>"
        + _ul(rejected, "No observation was rejected."),
    )


def _autonomy(run: MissionRun) -> str:
    if not run.autonomy_log:
        return _section("Onboard autonomy", '<p class="muted">No autonomy decisions logged.</p>')
    rows = []
    for d in run.autonomy_log:
        utilities = "; ".join(
            f"{c.action_id} {c.utility:.2f}" + ("" if c.feasible else f" ({c.rejection_reason})")
            for c in d.candidates
        )
        belief = ", ".join(f"{h.hypothesis_id} {_pct(h.probability)}" for h in d.belief.hypotheses)
        rows.append(
            [
                _e("ONBOARD" if d.decision_maker == "onboard-policy" else "GROUND"),
                _e(d.policy),
                _e(belief or "no hypothesis model"),
                _e(utilities or "none"),
                _e(d.selected_action_id or "hold"),
                _e(d.reason),
            ]
        )
    return _section(
        "Onboard autonomy",
        '<p class="muted">One-step policy selector over planned observations during '
        "communication blackouts (gameplay-estimate weights), not a POMDP planner.</p>"
        + _table(
            ["Authority", "Policy", "Input belief", "Candidate utilities", "Selected", "Reason"],
            rows,
        ),  # fmt: skip
    )


def _health(research: ResearchEvidence) -> str:
    items = [
        f"{f.anomaly.severity.upper()} {f.anomaly.channel} day {_num(f.anomaly.window_start)}"
        f"–{_num(f.anomaly.window_end)}: {f.anomaly.explanation} {f.explanation}"
        for f in research.health_findings
    ]
    return _section(
        "Health monitor",
        '<p class="muted">EWMA residual against the nominal model (same design and seed, no '
        "anomalies); transparent thresholds, not a trained detector.</p>"
        + _ul(items, "No telemetry departed from the nominal model."),
    )


def _research_sections(run: MissionRun, research: ResearchEvidence | None) -> list[str]:
    if research is None:
        return [_autonomy(run)]
    return [
        _traceability(research),
        _pareto(research),
        _robustness(research),
        _schedule(research),
        _autonomy(run),
        _health(research),
    ]


def _limitations_section(run: MissionRun, research: ResearchEvidence | None = None) -> str:
    fixed = [
        "All catalogue values are illustrative gameplay estimates (R3), not NASA, JPL or vendor data.",  # noqa: E501
        "The simulation is a deterministic event model, not orbital propagation or a flight-software test.",  # noqa: E501
        "This passport is an educational record of a game run; it must not be used for real mission planning.",  # noqa: E501
        NON_ENDORSEMENT,
    ]
    return _section(
        "Limitations",
        f"<h3>This run</h3>{_ul(run.final_report.limitations, 'No run limitations were reported.')}"
        f"<h3>This passport</h3>{_ul(fixed, '')}"
        + (
            f"<h3>Not included</h3>{_ul(research.not_included, '')}" if research is not None else ""
        ),
    )


def render_html(
    run: MissionRun,
    catalog: Mapping[str, CatalogComponent],
    records: list[EvidenceRecord],
    analysis: MissionAnalysis | None,
    replay: ReplayCheck | None,
    exported_at: datetime,
    app_version: str,
    *,
    research: ResearchEvidence | None = None,
) -> str:
    title = run.input_snapshot.title
    unverified = _unverified_text(replay)
    unverified_banner = (
        f'<p class="banner unverified" role="alert">{_e(unverified)}</p>' if unverified else ""
    )
    body = "".join(
        [
            _summary(run, analysis, replay),
            _brief(run, catalog),
            _architecture(run, catalog),
            _budgets(run, analysis),
            _timeline(run),
            _anomalies(run),
            _science(run),
            _score(run),
            *_research_sections(run, research),
            _manifest(run, app_version, exported_at, replay),
            _ledger(records, analysis),
            _limitations_section(run, research),
        ]
    )
    return (
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>MISSIONFORGE Evidence Passport: {_e(title)}</title><style>{_CSS}</style></head>"
        f"<body><main><header><h1>Evidence Passport: {_e(title)}</h1>"
        f'<p class="muted">Run <span class="mono">{_e(run.run_id)}</span> · exported {_e(_ts(exported_at))}</p>'  # noqa: E501
        f"{unverified_banner}"
        f'<p class="banner">{_e(NON_ENDORSEMENT)}</p></header>{body}'
        f"<footer>{_e(NON_ENDORSEMENT)}</footer></main></body></html>\n"
    )
