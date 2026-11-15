from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_versions() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["data"]["engineVersion"] == "0.1.0"
    assert body["data"]["catalogVersion"] == "0.1.0"
    assert body["data"]["jplAdapter"]["status"] in {"live", "cached", "demo", "unknown"}
    assert body["meta"]["requestId"]
    assert response.headers["x-request-id"] == body["meta"]["requestId"]
    text = response.text
    for forbidden in ("JPL_", "APP_CONTACT_EMAIL", "team@example.com", "NEXT_PUBLIC"):
        assert forbidden not in text


def test_unhandled_error_maps_to_internal_error_envelope() -> None:
    from fastapi import FastAPI

    from app.main import create_app

    boom_app: FastAPI = create_app()

    @boom_app.get("/api/boom")
    def boom() -> None:
        raise RuntimeError("secret detail")

    response = TestClient(boom_app, raise_server_exceptions=False).get("/api/boom")
    assert response.status_code == 500
    body = response.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "INTERNAL_ERROR"
    assert "secret detail" not in response.text
    assert body["meta"]["requestId"]


def test_cors_limited_to_frontend_origin() -> None:
    ok = client.get("/api/health", headers={"Origin": "http://localhost:3000"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:3000"
    # the same dev server opened by IP must work too (judging-laptop risk)
    ip = client.get("/api/health", headers={"Origin": "http://127.0.0.1:3000"})
    assert ip.headers.get("access-control-allow-origin") == "http://127.0.0.1:3000"
    bad =client.get("/api/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in bad.headers


def test_health_versions_ignore_env_overrides(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """R40: ENGINE_VERSION / CATALOG_VERSION env vars cannot change reported versions."""
    from fastapi.testclient import TestClient

    from app.config import get_settings
    from app.main import create_app

    monkeypatch.setenv("ENGINE_VERSION", "9.9.9")
    monkeypatch.setenv("CATALOG_VERSION", "9.9.9")
    get_settings.cache_clear()
    try:
        data = TestClient(create_app()).get("/api/health").json()["data"]
    finally:
        get_settings.cache_clear()
    assert data["engineVersion"] == "0.1.0"
    assert data["catalogVersion"] == "0.1.0"
