from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

from fastapi.testclient import TestClient

from api.main import create_app
from api.ragControll import get_current_user
from storage.models import KbMemberStatus


@contextmanager
def _fake_session():
    yield object()


class _FakeKnowledgeBaseStore:
    kb = SimpleNamespace(
        id="kb-1",
        tenant_id="tenant-a",
        owner_id="owner-user",
        name="Owner KB",
        description="",
        share_code=None,
        created_at=None,
        updated_at=None,
    )

    @staticmethod
    def get(_db, _kb_id):
        return _FakeKnowledgeBaseStore.kb


class _NoMembershipStore:
    @staticmethod
    def get_by_user_and_kb(_db, _user_id, _kb_id):
        return None


class _PendingMembershipStore:
    @staticmethod
    def get_by_user_and_kb(_db, _user_id, _kb_id):
        return SimpleNamespace(status=KbMemberStatus.pending)


class _ApprovedMembershipStore:
    @staticmethod
    def get_by_user_and_kb(_db, _user_id, _kb_id):
        return SimpleNamespace(status=KbMemberStatus.approved)


def _patch_kb_stores(monkeypatch, member_store) -> None:
    import api.ragControll as rag
    import services.kb_service as kb_service

    monkeypatch.setattr(rag, "KnowledgeBaseStore", _FakeKnowledgeBaseStore)
    monkeypatch.setattr(rag, "KbMemberStore", member_store)
    monkeypatch.setattr(kb_service, "KnowledgeBaseStore", _FakeKnowledgeBaseStore)
    monkeypatch.setattr(kb_service, "KbMemberStore", member_store)


def _client_as(monkeypatch, user: dict) -> TestClient:
    import api.ragControll as rag

    monkeypatch.setattr(rag, "get_session", _fake_session)
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def test_cross_tenant_user_cannot_read_knowledge_base(monkeypatch) -> None:
    _patch_kb_stores(monkeypatch, _NoMembershipStore)
    client = _client_as(
        monkeypatch,
        {"user_id": "outsider-user", "tenant_id": "tenant-b"},
    )

    response = client.get("/api/knowledge_bases/kb-1")

    assert response.status_code in (403, 404)


def test_pending_member_cannot_search_knowledge_base(monkeypatch) -> None:
    import api.ragControll as rag

    _patch_kb_stores(monkeypatch, _PendingMembershipStore)
    monkeypatch.setattr(rag, "_single_embed", lambda _query: [0.1, 0.2])
    monkeypatch.setattr(rag._search_service, "search", lambda **_kwargs: [])
    client = _client_as(
        monkeypatch,
        {"user_id": "pending-user", "tenant_id": "tenant-a"},
    )

    response = client.get("/api/search/kb-1", params={"query": "hello"})

    assert response.status_code == 403


def test_approved_member_can_search_knowledge_base(monkeypatch) -> None:
    import api.ragControll as rag

    _patch_kb_stores(monkeypatch, _ApprovedMembershipStore)
    monkeypatch.setattr(rag, "_single_embed", lambda _query: [0.1, 0.2])
    monkeypatch.setattr(rag._search_service, "search", lambda **_kwargs: [])
    client = _client_as(
        monkeypatch,
        {"user_id": "member-user", "tenant_id": "tenant-a"},
    )

    response = client.get("/api/search/kb-1", params={"query": "hello"})

    assert response.status_code == 200
    assert response.json()["results"] == []


def test_non_owner_cannot_delete_knowledge_base(monkeypatch) -> None:
    _patch_kb_stores(monkeypatch, _ApprovedMembershipStore)
    client = _client_as(
        monkeypatch,
        {"user_id": "member-user", "tenant_id": "tenant-a"},
    )

    response = client.delete("/api/knowledge_bases/kb-1")

    assert response.status_code == 403


def test_knowledge_base_routes_use_centralized_authorization_helpers() -> None:
    source = __import__("pathlib").Path("api/ragControll.py").read_text(encoding="utf-8")

    assert "require_kb_access(db, kb_id, user)" in source
    assert "require_kb_access(db, knowledge_base_id, user)" in source
    assert "require_kb_editor_or_owner(db, knowledge_base_id, user)" in source
    assert "require_kb_owner(db, kb_id, user)" in source


def test_upload_authorizes_before_reading_file() -> None:
    source = __import__("pathlib").Path("api/ragControll.py").read_text(encoding="utf-8")

    start = source.index("async def upload_file")
    end = source.index("\n\nasync def process_uploaded_document", start)
    handler = source[start:end]

    assert handler.index("require_kb_editor_or_owner") < handler.index("await file.read()")
