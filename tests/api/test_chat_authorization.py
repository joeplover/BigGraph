from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from api.main import create_app
from api.ragControll import get_current_user


def _client_as(user: dict) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def _patch_session_owner(monkeypatch, owner_user_id: str) -> None:
    import services.chat_service as chat_service

    monkeypatch.setattr(
        chat_service,
        "get_chat_session",
        lambda _session_id: {"id": "session-a", "user_id": owner_user_id, "title": "Owned"},
        raising=False,
    )


def test_user_cannot_rename_another_users_chat_session(monkeypatch) -> None:
    import api.ragControll as rag

    _patch_session_owner(monkeypatch, owner_user_id="owner-user")
    calls = []
    monkeypatch.setattr(rag, "rename_chat_session", lambda *args: calls.append(args))
    client = _client_as({"user_id": "other-user", "tenant_id": "tenant-a"})

    response = client.patch("/api/chat/sessions/session-a", json={"title": "Stolen"})

    assert response.status_code == 403
    assert calls == []


def test_user_cannot_read_another_users_chat_history(monkeypatch) -> None:
    import api.ragControll as rag

    _patch_session_owner(monkeypatch, owner_user_id="owner-user")
    monkeypatch.setattr(rag, "get_chat_history", lambda _session_id: [{"role": "user", "content": "secret"}])
    client = _client_as({"user_id": "other-user", "tenant_id": "tenant-a"})

    response = client.get("/api/chat/history/session-a")

    assert response.status_code == 403


def test_chat_request_cannot_append_to_another_users_session(monkeypatch) -> None:
    import api.ragControll as rag

    _patch_session_owner(monkeypatch, owner_user_id="owner-user")
    monkeypatch.setattr(rag, "get_chat_history", lambda _session_id: [])
    monkeypatch.setattr(rag, "save_chat_message", lambda *_args: None)
    monkeypatch.setattr(rag, "chat_llm", SimpleNamespace(invoke=lambda _messages: SimpleNamespace(content="ok")))
    client = _client_as({"user_id": "other-user", "tenant_id": "tenant-a"})

    response = client.post(
        "/api/chat",
        json={"message": "write into someone else's session", "session_id": "session-a"},
    )

    assert response.status_code == 403


def test_owner_can_read_own_chat_history(monkeypatch) -> None:
    import api.ragControll as rag

    _patch_session_owner(monkeypatch, owner_user_id="owner-user")
    monkeypatch.setattr(rag, "get_chat_history", lambda _session_id: [{"role": "user", "content": "mine"}])
    client = _client_as({"user_id": "owner-user", "tenant_id": "tenant-a"})

    response = client.get("/api/chat/history/session-a")

    assert response.status_code == 200
    assert response.json()["messages"] == [{"role": "user", "content": "mine"}]
