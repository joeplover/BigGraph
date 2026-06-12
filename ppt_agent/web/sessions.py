from copy import deepcopy
from uuid import uuid4

from ppt_agent.state import State
from ppt_agent.web.materials import summarize_materials


class SessionStore:
    """In-memory LangGraph state store for the web app."""

    def __init__(self) -> None:
        self._sessions: dict[str, State] = {}

    def create(self) -> tuple[str, State]:
        session_id = uuid4().hex
        state: State = {
            "messages": [],
            "requirement": {},
            "material": _empty_material(),
        }
        self._sessions[session_id] = state
        return session_id, deepcopy(state)

    def get_or_create(self, session_id: str | None) -> tuple[str, State]:
        if session_id and session_id in self._sessions:
            return session_id, deepcopy(self._sessions[session_id])
        return self.create()

    def save(self, session_id: str, state: State) -> State:
        self._sessions[session_id] = deepcopy(state)
        return deepcopy(state)

    def add_materials(
        self,
        session_id: str | None,
        filenames: list[str],
        texts: list[str],
    ) -> tuple[str, State]:
        session_id, state = self.get_or_create(session_id)
        material = state.get("material") or _empty_material()

        raw_texts = list(material.get("raw_texts", [])) + texts
        file_paths = list(material.get("file_paths", [])) + filenames
        summary = summarize_materials(raw_texts)

        material = {
            "raw_texts": raw_texts,
            "file_paths": file_paths,
            "summary": summary,
            "topic": summary.get("topic", ""),
            "keywords": summary.get("keywords", []),
            "key_points": summary.get("key_points", []),
        }
        state["material"] = material
        state["status"] = "material_ready"

        requirement = state.get("requirement", {})
        if summary.get("topic") and not requirement.get("topic"):
            requirement = {**requirement, "topic": summary["topic"]}
        if summary.get("key_points"):
            requirement = {**requirement, "key_points": summary["key_points"]}
        state["requirement"] = requirement

        return session_id, self.save(session_id, state)


def _empty_material() -> dict:
    return {
        "raw_texts": [],
        "file_paths": [],
        "summary": {},
        "topic": "",
        "keywords": [],
        "key_points": [],
    }
