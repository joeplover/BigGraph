from pathlib import Path


def test_api_chat_session_route_exists_before_static_fallback() -> None:
    source = Path("api/ragControll.py").read_text(encoding="utf-8")

    assert '@app.post("/api/chat/sessions")' in source
    assert '@app.get("/api/chat/sessions")' in source
    assert '@app.patch("/api/chat/sessions/{session_id}")' in source


def test_api_chat_route_exists_before_static_fallback() -> None:
    source = Path("api/ragControll.py").read_text(encoding="utf-8")

    assert '@app.post("/api/chat")' in source
    assert '@app.get("/api/chat/history/{session_id}")' in source
    assert '@app.delete("/api/chat/history/{session_id}")' in source
