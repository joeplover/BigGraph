from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

from fastapi.testclient import TestClient

from api.main import create_app
from api.ragControll import get_current_user
from storage.models import IngestionJobStatus


@contextmanager
def _fake_session():
    yield object()


def _client_with_job(monkeypatch, status: IngestionJobStatus, error_message: str | None = None) -> TestClient:
    import api.ragControll as rag

    job = SimpleNamespace(
        id="job-1",
        status=status,
        progress=42,
        error_message=error_message,
        created_at=None,
        updated_at=None,
    )
    monkeypatch.setattr(rag, "get_session", _fake_session)
    monkeypatch.setattr(rag.IngestionJobStore, "get", lambda _db, _job_id: job)

    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: {
        "user_id": "owner-user",
        "tenant_id": "tenant-a",
    }
    return TestClient(app)


def test_failed_job_status_exposes_stable_error_code(monkeypatch) -> None:
    client = _client_with_job(monkeypatch, IngestionJobStatus.failed, "parser exploded")

    response = client.get("/api/jobs/job-1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "failed"
    assert payload["state"] == "failed"
    assert payload["error_code"] == "ingestion_failed"
    assert payload["error_message"] == "parser exploded"


def test_in_progress_job_status_maps_to_running_state(monkeypatch) -> None:
    client = _client_with_job(monkeypatch, IngestionJobStatus.embedding)

    response = client.get("/api/jobs/job-1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "embedding"
    assert payload["state"] == "running"
    assert payload["error_code"] == ""
