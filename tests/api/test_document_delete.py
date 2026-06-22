from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

from fastapi.testclient import TestClient

from api.main import create_app
from api.ragControll import get_current_user


@contextmanager
def _fake_session():
    yield object()


class _FakeDocumentStore:
    updates = []

    @staticmethod
    def get(_db, _doc_id):
        return SimpleNamespace(id="doc-1", tenant_id="tenant-a", knowledge_base_id="kb-1")

    @staticmethod
    def update_status(_db, doc_id, status):
        _FakeDocumentStore.updates.append((doc_id, status))


class _FakeDocumentChunkStore:
    @staticmethod
    def delete_by_document(_db, _doc_id):
        return 3


class _FakeKnowledgeBaseStore:
    @staticmethod
    def get(_db, _kb_id):
        return SimpleNamespace(id="kb-1", tenant_id="tenant-a", owner_id="owner-user")


def _client_with_document_fakes(monkeypatch, user: dict) -> TestClient:
    import api.ragControll as rag
    import services.kb_service as kb_service

    _FakeDocumentStore.updates = []
    monkeypatch.setattr(rag, "get_session", _fake_session)
    monkeypatch.setattr(rag, "DocumentStore", _FakeDocumentStore)
    monkeypatch.setattr(rag, "DocumentChunkStore", _FakeDocumentChunkStore)
    monkeypatch.setattr(kb_service, "KnowledgeBaseStore", _FakeKnowledgeBaseStore)

    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def test_non_owner_cannot_delete_document(monkeypatch) -> None:
    import api.ragControll as rag

    monkeypatch.setattr(rag._qdrant, "delete_document_vectors", lambda **_kwargs: None)
    monkeypatch.setattr(rag._es, "delete_document_chunks", lambda **_kwargs: None)
    client = _client_with_document_fakes(
        monkeypatch,
        {"user_id": "other-user", "tenant_id": "tenant-a"},
    )

    response = client.delete("/api/documents/doc-1")

    assert response.status_code == 403
    assert _FakeDocumentStore.updates == []


def test_document_delete_reports_external_cleanup_errors(monkeypatch) -> None:
    import api.ragControll as rag

    monkeypatch.setattr(
        rag._qdrant,
        "delete_document_vectors",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("qdrant down")),
    )
    monkeypatch.setattr(
        rag._es,
        "delete_document_chunks",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("es down")),
    )
    client = _client_with_document_fakes(
        monkeypatch,
        {"user_id": "owner-user", "tenant_id": "tenant-a"},
    )

    response = client.delete("/api/documents/doc-1")

    assert response.status_code == 200
    assert response.json()["cleanup_errors"] == [
        "qdrant:qdrant down",
        "elasticsearch:es down",
    ]
