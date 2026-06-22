from api import ppt_agent_router


def test_background_ppt_task_persists_assistant_reply(monkeypatch):
    saved_messages: list[tuple[str, str, str]] = []
    saved_states: list[tuple[str, dict]] = []
    saved_results: list[tuple[str, str, str, str]] = []
    notifications: list[tuple[str, dict]] = []

    def fake_invoke(state):
        return {
            **state,
            "assistant_reply": "PPT plan ready",
            "status": "waiting_confirm",
        }

    monkeypatch.setattr(ppt_agent_router.ppt_graph, "invoke", fake_invoke)
    monkeypatch.setattr(
        ppt_agent_router,
        "save_ppt_state",
        lambda session_id, state: saved_states.append((session_id, state)),
    )
    monkeypatch.setattr(
        ppt_agent_router,
        "save_chat_message",
        lambda session_id, role, content: saved_messages.append((session_id, role, content)),
    )
    monkeypatch.setattr(
        ppt_agent_router,
        "save_ppt_task_result",
        lambda session_id, response, pptx_download_url, status: saved_results.append(
            (session_id, response, pptx_download_url, status)
        ),
    )
    monkeypatch.setattr(
        ppt_agent_router,
        "_notify_ppt_done",
        lambda session_id, result: notifications.append((session_id, result)),
    )

    ppt_agent_router._run_ppt_graph_in_background(
        session_id="session-1",
        state={"messages": [], "requirement": {}},
        message="make a deck",
    )

    assert saved_states[0][0] == "session-1"
    assert saved_messages == [
        ("session-1", "user", "make a deck"),
        ("session-1", "assistant", "PPT plan ready"),
    ]
    assert saved_results == [("session-1", "PPT plan ready", "", "done")]
    assert notifications == [
        (
            "session-1",
            {
                "status": "done",
                "response": "PPT plan ready",
                "pptx_download_url": "",
            },
        )
    ]
