"""Application settings, read from environment variables (server-side only)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "MISSIONFORGE"
    app_version: str = "0.1.0"
    app_contact_email: str = "team@example.com"

    jpl_mdesign_base_url: str = "https://ssd-api.jpl.nasa.gov/mdesign.api"
    jpl_request_timeout_ms: int = 10000
    jpl_cache_ttl_a_seconds: int = 43200
    jpl_cache_ttl_q_seconds: int = 86400
    jpl_cache_ttl_m_seconds: int = 21600

    mission_schema_version: str = "1.0"
    # R40: there is no engine/catalogue version setting. The engine version is
    # app.domain.analysis.orchestrator.ENGINE_VERSION and the catalogue version is the
    # loaded catalogue's own `version`, so an env var can never make them disagree.

    cors_origins: list[str] = ["http://localhost:3000"]

    # Request body limit (architecture 13): bodies above this are rejected with 413.
    max_request_bytes: int = 256 * 1024

    # Mission packages carry whole runs (~80 KiB each, up to 20), so /api/mission/import gets a
    # dedicated higher limit. /api/mission/replay takes one run and keeps the default.
    max_import_bytes: int = 4 * 1024 * 1024

    # Monte Carlo cap for /mission/simulate (architecture 11.3 SIMULATION_LIMIT_EXCEEDED).
    max_monte_carlo_samples: int = 1000


@lru_cache
def get_settings() -> Settings:
    return Settings()


# <repo>/data/catalog (backend/app/config.py -> parents[2] is the repo root). Kept here, not in
# the pure domain layer, which only ever receives an explicit path.
DEFAULT_CATALOG_DIR = Path(__file__).resolve().parents[2] / "data" / "catalog"

# <repo>/data/missions: scenario templates (explicit path passed into the pure domain layer).
DEFAULT_MISSIONS_DIR = Path(__file__).resolve().parents[2] / "data" / "missions"

# <repo>/data/demo/demo-saved.json: seeded demo mission package (Task 7.5). Not in
# data/missions, whose every *.json is read as a scenario template.
DEFAULT_DEMO_PACKAGE = Path(__file__).resolve().parents[2] / "data" / "demo" / "demo-saved.json"

# <repo>/data/scenarios: scenario event sets (explicit path passed into the simulation).
DEFAULT_SCENARIOS_DIR = Path(__file__).resolve().parents[2] / "data" / "scenarios"
