from fastapi.testclient import TestClient

from api import ppt_agent_router
from api.main import create_app


def test_ppt_status_recovers_persisted_failure_error_code(monkeypatch) -> None:
    monkeypatch.setattr(
        ppt_agent_router,
        "get_ppt_task_status",
        lambda _session_id: {
            "status": "failed",
            "response": "PPT generation failed",
            "pptx_download_url": "",
            "error_code": "ppt_generation_failed",
        },
    )
    client = TestClient(create_app())

    response = client.get("/api/ppt/status/session-1")

    assert response.status_code == 200
    assert response.json() == {
        "status": "failed",
        "response": "PPT generation failed",
        "pptx_download_url": "",
        "error_code": "ppt_generation_failed",
    }
