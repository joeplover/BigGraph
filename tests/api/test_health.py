from fastapi.testclient import TestClient

from api.main import create_app


def test_health_returns_ok_without_dependency_checks():
    client = TestClient(create_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "biggraph",
        "version": "1.0.0",
    }


def test_dependency_health_reports_degraded_when_optional_services_fail(monkeypatch):
    client = TestClient(create_app())

    monkeypatch.setattr("api.main._check_postgres", lambda: "ok")
    monkeypatch.setattr("api.main._check_redis", lambda: "ok")
    monkeypatch.setattr("api.main._check_qdrant", lambda: "unavailable")
    monkeypatch.setattr("api.main._check_elasticsearch", lambda: "ok")

    response = client.get("/api/health/dependencies")

    assert response.status_code == 200
    assert response.json() == {
        "status": "degraded",
        "dependencies": {
            "postgres": "ok",
            "redis": "ok",
            "qdrant": "unavailable",
            "elasticsearch": "ok",
        },
    }


def test_dependency_health_reports_failed_when_postgres_fails(monkeypatch):
    client = TestClient(create_app())

    monkeypatch.setattr("api.main._check_postgres", lambda: "unavailable")
    monkeypatch.setattr("api.main._check_redis", lambda: "ok")
    monkeypatch.setattr("api.main._check_qdrant", lambda: "ok")
    monkeypatch.setattr("api.main._check_elasticsearch", lambda: "ok")

    response = client.get("/api/health/dependencies")

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
