from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

from fastapi.testclient import TestClient

from api.main import create_app
from api.ragControll import get_current_user


@contextmanager
def _fake_session():
    yield object()


class _FakeKnowledgeBaseStore:
    @staticmethod
    def get(_db, _kb_id):
        return SimpleNamespace(id="kb-1", tenant_id="tenant-a", owner_id="owner-user")


class _FakeUploadedFileStore:
    @staticmethod
    def create(**_kwargs):
        return SimpleNamespace(id="file-1")


class _FakeIngestionJobStore:
    @staticmethod
    def create(**_kwargs):
        return SimpleNamespace(id="job-1")


def _client_with_upload_fakes(monkeypatch, tmp_path) -> TestClient:
    import api.ragControll as rag
    import services.kb_service as kb_service

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(rag, "get_session", _fake_session)
    monkeypatch.setattr(rag, "UploadedFileStore", _FakeUploadedFileStore)
    monkeypatch.setattr(rag, "IngestionJobStore", _FakeIngestionJobStore)
    monkeypatch.setattr(rag, "process_uploaded_document", lambda *_args: None)
    monkeypatch.setattr(kb_service, "KnowledgeBaseStore", _FakeKnowledgeBaseStore)

    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: {
        "user_id": "owner-user",
        "tenant_id": "tenant-a",
    }
    return TestClient(app)


def test_upload_rejects_unsupported_file_type(monkeypatch, tmp_path) -> None:
    client = _client_with_upload_fakes(monkeypatch, tmp_path)

    response = client.post(
        "/api/upload/kb-1",
        files={"file": ("malware.exe", b"not a document", "application/octet-stream")},
    )

    assert response.status_code == 400


def test_upload_rejects_file_over_size_limit(monkeypatch, tmp_path) -> None:
    import api.ragControll as rag

    monkeypatch.setattr(rag, "MAX_UPLOAD_BYTES", 4, raising=False)
    client = _client_with_upload_fakes(monkeypatch, tmp_path)

    response = client.post(
        "/api/upload/kb-1",
        files={"file": ("notes.txt", b"12345", "text/plain")},
    )

    assert response.status_code == 400


def test_upload_accepts_supported_file_under_size_limit(monkeypatch, tmp_path) -> None:
    import api.ragControll as rag

    monkeypatch.setattr(rag, "MAX_UPLOAD_BYTES", 1024, raising=False)
    client = _client_with_upload_fakes(monkeypatch, tmp_path)

    response = client.post(
        "/api/upload/kb-1",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 200
    assert response.json()["job_id"] == "job-1"
