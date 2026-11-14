"""Evidence Passport domain tests (Task 4.6, architecture 19.9, M18 acceptance)."""

import json
import re
from typing import Any

import pytest

from app.domain.dossier.build_run_manifest import build_run_manifest
from app.domain.dossier.export_mission_dossier import (
    NON_ENDORSEMENT,
    Dossier,
    ReplayCheck,
    build_evidence_records,
    export_mission_dossier,
)
from app.schemas.evidence import MissionPackage
from app.schemas.simulation import MissionRun
from tests.unit.dossier.conftest import EXPORTED, Env

UNAVAILABLE = "unavailable-source"


def _export(env: Env, run: MissionRun, **kw: Any) -> Dossier:
    return export_mission_dossier(
        run,
        env.catalog,
        exported_at=EXPORTED,
        app_version="0.1.0",
        analysis=env.analysis(run),
        **kw,
    )


def _with_outcome(run: MissionRun, outcome: str, summary: str) -> MissionRun:
    dump = run.model_dump()
    dump["final_report"]["outcome"] = outcome
    dump["final_report"]["summary"] = summary
    return MissionRun.model_validate(dump)


def _summary(html: str) -> str:
    return html.split("Executive summary</h2>")[1].split("</section>")[0]


def test_manifest_has_all_fields(run: MissionRun) -> None:
    m = build_run_manifest(run, app_version="9.9.9")
    dumped = m.model_dump(by_alias=True)
    assert set(dumped) == {
        "schemaVersion", "engineVersion", "catalogVersion", "scenarioVersion",
        "eventSetId", "seed", "appVersion",
    }  # fmt: skip
    assert m.seed == run.seed and m.event_set_id == run.scenario_event_set_id
    assert m.engine_version == run.engine_version and m.catalog_version == run.catalog_version
    assert m.scenario_version == run.manifest.scenario_version
    assert m.app_version == "9.9.9"
    assert all(v not in ("", None) for v in dumped.values())


def test_every_evidence_record_has_a_source_link_or_unavailable_label(
    env: Env, run: MissionRun
) -> None:
    records = build_evidence_records(run, env.catalog, analysis=env.analysis(run))
    assert records
    ids = [r.id for r in records]
    assert len(ids) == len(set(ids))
    for r in records:
        assert r.source_title, r.id
        if r.fidelity != "derived":
            assert r.source_url or any(x.startswith(UNAVAILABLE) for x in r.limitations), r.id


def test_catalogue_values_are_gameplay_estimates_with_archetype_source(
    env: Env, run: MissionRun
) -> None:
    records = build_evidence_records(run, env.catalog)
    comp = [r for r in records if r.id.startswith("ev-component-")]
    arch = run.input_snapshot.architecture
    assert {r.subject_id.split(".")[0] for r in comp} >= {arch.bus_id, arch.communications_id}
    assert all(r.fidelity == "gameplay-estimate" for r in comp)  # R3: nothing source-backed
    assert all(r.source_title == "MISSIONFORGE illustrative archetype v0.1.0" for r in comp)
    assert all("unavailable-source: no primary source audited yet" in r.limitations for r in comp)
    assert not any(r.fidelity == "source-backed" for r in records)


def test_trajectory_values_are_scenario_preset_estimates(env: Env, run: MissionRun) -> None:
    records = build_evidence_records(run, env.catalog)
    traj = [r for r in records if r.id.startswith("ev-trajectory-")]
    assert traj and all(r.fidelity == "gameplay-estimate" for r in traj)
    assert any(r.subject_id == "trajectory.mission_delta_v_km_per_s" for r in traj)


def test_jpl_trajectory_is_source_backed_only_with_a_reference(env: Env, run: MissionRun) -> None:
    dump = run.model_dump()
    dump["input_snapshot"]["trajectory"]["provider"] = "jpl-mdesign"
    dump["input_snapshot"]["trajectory"]["raw_source_ref"] = "https://example.org/jpl/ref"
    with_ref = MissionRun.model_validate(dump)
    traj = [r for r in build_evidence_records(with_ref, env.catalog) if "trajectory" in r.id]
    assert traj and all(r.fidelity == "source-backed" and r.source_url for r in traj)
    dump["input_snapshot"]["trajectory"]["raw_source_ref"] = None
    no_ref = MissionRun.model_validate(dump)
    traj = [r for r in build_evidence_records(no_ref, env.catalog) if "trajectory" in r.id]
    assert all(UNAVAILABLE in " ".join(r.limitations) for r in traj)
    assert not any(r.fidelity == "source-backed" for r in traj)


def test_derived_budgets_are_engine_derived(env: Env, run: MissionRun) -> None:
    records = build_evidence_records(run, env.catalog, analysis=env.analysis(run))
    budgets = [r for r in records if r.id.startswith("ev-budget-")]
    assert len(budgets) >= 10
    assert all(r.source_version == run.engine_version for r in budgets)
    assert sum(r.fidelity == "derived" for r in budgets) >= 9
    # cost keeps its own honest label: a sum of gameplay-estimate catalogue costs is not "derived"
    assert next(r for r in budgets if "cost" in r.id).fidelity == "gameplay-estimate"
    assert not [r for r in build_evidence_records(run, env.catalog) if r.id.startswith("ev-budget")]


def test_unknown_component_is_not_modelled_not_a_crash(env: Env, run: MissionRun) -> None:
    dump = run.model_dump()
    dump["input_snapshot"]["architecture"]["bus_id"] = "bus-does-not-exist"
    odd = MissionRun.model_validate(dump)
    rec = [r for r in build_evidence_records(odd, env.catalog) if "bus-does-not-exist" in r.id]
    assert len(rec) == 1 and rec[0].fidelity == "not-modelled"
    assert any(x.startswith(UNAVAILABLE) for x in rec[0].limitations)


def test_package_validates_and_round_trips(env: Env, run: MissionRun) -> None:
    pkg = _export(env, run).package
    assert pkg.exported_at == EXPORTED
    assert pkg.mission == run.input_snapshot and pkg.runs == [run]
    assert pkg.manifest.app_version == "0.1.0"
    assert pkg.manifest.scenario_version == run.manifest.scenario_version
    assert pkg.evidence
    again = MissionPackage.model_validate_json(pkg.model_dump_json(by_alias=True))
    assert again == pkg
    json.loads(pkg.model_dump_json(by_alias=True))  # plain JSON, no NaN literal


def test_html_is_self_contained_and_has_every_section(env: Env, run: MissionRun) -> None:
    html = _export(env, run).html
    assert html.startswith("<!doctype html>")
    assert "@media print" in html
    assert not re.search(r"<script|<link |src=|@import|url\(", html, re.I)
    for section in (
        "Executive summary", "Mission brief", "Selected architecture", "Budgets and margins",
        "Operations timeline", "Anomalies and realized risks", "Science collected and returned",
        "Score breakdown", "Run manifest", "Sources and assumptions", "Limitations",
    ):  # fmt: skip
        assert f">{section}</h2>" in html, section
    assert NON_ENDORSEMENT in html
    assert "not a NASA/JPL product or endorsement" in html
    for r in build_evidence_records(run, env.catalog, analysis=env.analysis(run)):
        assert r.id in html  # the ledger lists every evidence record
    for key in (run.engine_version, run.catalog_version, run.scenario_event_set_id, str(run.seed)):
        assert key in html


def test_html_escapes_user_and_catalogue_strings(env: Env, run: MissionRun) -> None:
    evil = "<script>alert(1)</script>"
    dump = run.model_dump()
    dump["input_snapshot"]["science_objectives"][0]["title"] = evil
    dump["input_snapshot"]["science_objectives"][0]["question"] = '"><img src=x onerror=alert(2)>'
    dump["final_report"]["summary"] = "<b>bold</b> & more"
    dump["final_report"]["root_causes"] = ["<i>x</i>"]
    hostile = MissionRun.model_validate(dump)
    html = _export(env, hostile).html
    assert "<script>" not in html and "<img" not in html and "<b>bold" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "&lt;b&gt;bold&lt;/b&gt; &amp; more" in html
    assert "&lt;i&gt;x&lt;/i&gt;" in html


def test_deterministic_apart_from_exported_at(env: Env, run: MissionRun) -> None:
    a = _export(env, run)
    b = _export(env, run)
    assert a.html == b.html
    assert a.package.model_dump_json(by_alias=True) == b.package.model_dump_json(by_alias=True)
    later = export_mission_dossier(
        run,
        env.catalog,
        exported_at=EXPORTED.replace(hour=20),
        app_version="0.1.0",
        analysis=env.analysis(run),
    )
    assert "2026-11-14T13:00:00Z" in a.html
    assert later.html.replace("2026-11-14T20:00:00Z", "X") == a.html.replace(
        "2026-11-14T13:00:00Z", "X"
    )


@pytest.mark.parametrize(
    ("outcome", "needle"),
    [
        ("success", "Mission success"),
        ("partial", "Partial success"),
        ("failure", "Mission failure"),
        ("terminated", "Mission terminated early"),
    ],
)
def test_outcomes_are_distinguishable(env: Env, run: MissionRun, outcome: str, needle: str) -> None:
    summary = _summary(_export(env, _with_outcome(run, outcome, "s")).html)
    assert needle in summary
    others = {"Mission success", "Partial success", "Mission failure", "Mission terminated early"}
    assert not any(o in summary for o in others - {needle})


def test_failed_mission_is_not_confused_with_incomplete_model(env: Env, run: MissionRun) -> None:
    summary = _summary(_export(env, _with_outcome(run, "failure", "lost")).html)
    assert "Model completeness" in summary
    assert "not a mission failure" in summary


def test_replay_check_is_reported_honestly(env: Env, run: MissionRun) -> None:
    none = _export(env, run).html
    assert "Replay was not verified" in none
    ok = _export(env, run, replay=ReplayCheck("identical-replay", ())).html
    assert "identical replay" in ok.lower() and "Replay was not verified" not in ok
    bad = _export(env, run, replay=ReplayCheck("version-mismatch", ("engineVersion",))).html
    assert "not an identical replay" in bad and "engineVersion" in bad


def test_missing_analysis_is_labelled_not_invented(env: Env, run: MissionRun) -> None:
    html = export_mission_dossier(run, env.catalog, exported_at=EXPORTED, app_version="0.1.0").html
    assert "Budgets were not available" in html


def test_experimental_run_is_flagged(env: Env) -> None:
    html = _export(env, env.run(experimental=True)).html
    assert "Experimental what-if" in html
