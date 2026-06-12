from pathlib import Path

from fastapi.testclient import TestClient

from ppt_agent.web.server import create_app


def test_upload_text_material_adds_it_to_session(tmp_path: Path) -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/materials",
        files={"files": ("paper.md", b"# Demo\n\nkeywords: agent ppt", "text/markdown")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["material"]["file_paths"] == ["paper.md"]
    assert payload["material"]["raw_texts"] == ["# Demo\n\nkeywords: agent ppt"]
    assert payload["state"]["status"] == "material_ready"


def test_upload_rejects_unsupported_file_type() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/materials",
        files={"files": ("deck.exe", b"nope", "application/octet-stream")},
    )

    assert response.status_code == 400
    assert "仅支持" in response.json()["detail"]


def test_chat_uses_existing_session_state(monkeypatch) -> None:
    client = TestClient(create_app())

    def fake_invoke(state):
        assert state["material"]["raw_texts"] == ["uploaded material"]
        return {
            **state,
            "assistant_reply": "收到",
            "status": "waiting_confirm",
            "requirement": {"topic": "Demo"},
        }

    monkeypatch.setattr("ppt_agent.web.server.graph_app.invoke", fake_invoke)

    upload_response = client.post(
        "/api/materials",
        files={"files": ("notes.txt", b"uploaded material", "text/plain")},
    )
    session_id = upload_response.json()["session_id"]

    response = client.post(
        "/api/chat",
        json={"message": "帮我做一个 PPT", "session_id": session_id},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == session_id
    assert payload["assistant_reply"] == "收到"
    assert payload["state"]["status"] == "waiting_confirm"


def test_chat_returns_download_link_without_local_pptx_path(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client = TestClient(create_app())
    pptx_path = tmp_path / "result.pptx"
    pptx_path.write_bytes(b"pptx bytes")

    def fake_invoke(state):
        return {
            **state,
            "assistant_reply": f"PPT 已生成：{pptx_path}",
            "status": "ppt_exported",
            "pptx_path": str(pptx_path),
        }

    monkeypatch.setattr("ppt_agent.web.server.graph_app.invoke", fake_invoke)

    response = client.post("/api/chat", json={"message": "确认"})

    assert response.status_code == 200
    payload = response.json()
    assert str(pptx_path) not in payload["assistant_reply"]
    assert "/api/download/" not in payload["assistant_reply"]
    assert payload["assistant_reply"] == "PPT 已生成，请点击页面中的“下载 PPT”按钮获取文件。"
    assert payload["state"]["pptx_path"] == ""
    assert payload["state"]["pptx_ready"] is True
    assert payload["state"]["pptx_download_url"] == (
        f"/api/download/{payload['session_id']}/pptx"
    )


def test_download_pptx_returns_generated_file(monkeypatch, tmp_path: Path) -> None:
    client = TestClient(create_app())
    pptx_path = tmp_path / "result.pptx"
    pptx_path.write_bytes(b"pptx bytes")

    def fake_invoke(state):
        return {
            **state,
            "assistant_reply": "PPT 已生成。",
            "status": "ppt_exported",
            "pptx_path": str(pptx_path),
        }

    monkeypatch.setattr("ppt_agent.web.server.graph_app.invoke", fake_invoke)

    chat_response = client.post("/api/chat", json={"message": "确认"})
    session_id = chat_response.json()["session_id"]

    response = client.get(f"/api/download/{session_id}/pptx")

    assert response.status_code == 200
    assert response.content == b"pptx bytes"
    assert response.headers["content-disposition"].startswith("attachment;")


def test_chat_hides_local_project_path(monkeypatch, tmp_path: Path) -> None:
    client = TestClient(create_app())
    project_path = tmp_path / "project"
    project_path.mkdir()

    def fake_invoke(state):
        return {
            **state,
            "assistant_reply": f"项目已创建：{project_path}",
            "status": "waiting_confirm",
            "project_path": str(project_path),
        }

    monkeypatch.setattr("ppt_agent.web.server.graph_app.invoke", fake_invoke)

    response = client.post("/api/chat", json={"message": "做 PPT"})

    assert response.status_code == 200
    payload = response.json()
    assert str(project_path) not in payload["assistant_reply"]
    assert payload["assistant_reply"] == (
        '项目资料已创建，请在页面中确认 PPT 制作方案。(回复"确认"开始创建ppt)'
    )
    assert payload["state"]["project_path"] == ""
    assert payload["state"]["project_ready"] is True
