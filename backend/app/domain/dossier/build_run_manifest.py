"""Run manifest for the Evidence Passport (architecture 19.9)."""

from app.schemas.simulation import MissionRun, MissionRunManifest


def build_run_manifest(run: MissionRun, *, app_version: str) -> MissionRunManifest:
    """The manifest a passport reports for `run`.

    Every version comes from the run itself (what it was actually produced with), never from
    the exporting server; only `app_version` is the exporter's. The result therefore always
    agrees with `run.manifest` apart from that stamp, which MissionRun validation enforces.
    """
    return MissionRunManifest(
        schema_version=run.input_snapshot.schema_version,
        engine_version=run.engine_version,
        catalog_version=run.catalog_version,
        scenario_version=run.manifest.scenario_version,
        event_set_id=run.scenario_event_set_id,
        seed=run.seed,
        app_version=app_version,
    )
