"""Evidence, run manifest and mission package contracts (module_breakdown 4.2D, M18;
architecture 19.9). Owner: product/data lead + integration lead (decision D1: domain code
lives in domain/dossier, schemas here).

Version fields are plain strings so an imported run made with a different engine /
catalogue version can still be represented and flagged as "not identical replay".
"""

from datetime import date, datetime
from typing import Literal

from pydantic import Field, StrictInt

from app.schemas.analysis import MissionAnalysis
from app.schemas.api import ContractModel
from app.schemas.mission import MissionState
from app.schemas.simulation import MissionRun
from app.schemas.units import Fidelity, Unit


class EvidenceRecord(ContractModel):
    id: str
    subject_id: str  # entity / parameter / result ID this evidence explains
    fidelity: Fidelity
    source_title: str | None = None
    source_url: str | None = None
    source_version: str | None = None  # source edition or API signature version
    retrieved_at: datetime | None = None
    published_at: date | None = None
    unit: Unit | None = None
    conversion_notes: str | None = None
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    related_ids: list[str] = Field(default_factory=list)  # analysis constraint / event IDs


class MissionRunManifest(ContractModel):
    schema_version: str
    engine_version: str
    catalog_version: str
    scenario_version: str
    event_set_id: str
    seed: StrictInt
    app_version: str


class MissionPackageManifest(ContractModel):
    app_version: str
    engine_version: str
    catalog_version: str
    scenario_version: str


class MissionPackage(ContractModel):
    package_schema_version: Literal["1.0"] = "1.0"
    exported_at: datetime
    mission: MissionState
    latest_analysis: MissionAnalysis | None = None  # derived; recalculated on import
    runs: list[MissionRun] = Field(default_factory=list)
    evidence: list[EvidenceRecord] = Field(default_factory=list)
    manifest: MissionPackageManifest
