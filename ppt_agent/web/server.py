from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from ppt_agent.graph import app as graph_app
from ppt_agent.state import State
from ppt_agent.web.materials import decode_material_bytes
from ppt_agent.web.sessions import SessionStore


WEB_DIR = Path(__file__).resolve().parent
STATIC_DIR = WEB_DIR / "static"


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    assistant_reply: str
    state: dict[str, Any]


def create_app() -> FastAPI:
    server = FastAPI(title="Growing Agent Web", version="0.1.0")
    store = SessionStore()
    server.state.sessions = store

    server.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if STATIC_DIR.exists():
        server.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @server.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @server.post("/api/sessions")
    def create_session() -> dict:
        session_id, state = store.create()
        return {"session_id": session_id, "state": _public_state(state)}

    @server.post("/api/materials")
    async def upload_materials(
        session_id: str | None = Form(default=None),
        files: list[UploadFile] = File(...),
    ) -> dict:
        uploaded_names = []
        uploaded_texts = []

        for upload in files:
            try:
                material = decode_material_bytes(upload.filename or "material.txt", await upload.read())
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

            uploaded_names.append(material.filename)
            uploaded_texts.append(material.text)

        active_session_id, state = store.add_materials(
            session_id,
            uploaded_names,
            uploaded_texts,
        )
        material_state = state.get("material", {})

        return {
            "session_id": active_session_id,
            "material": material_state,
            "state": _public_state(state),
        }

    @server.post("/api/chat", response_model=ChatResponse)
    def chat(request: ChatRequest) -> ChatResponse:
        message = request.message.strip()
        if not message:
            raise HTTPException(status_code=400, detail="消息不能为空。")

        session_id, state = store.get_or_create(request.session_id)
        state.pop("assistant_reply", None)
        state.setdefault("messages", [])
        state["messages"].append(HumanMessage(content=message))

        next_state = graph_app.invoke(state)
        store.save(session_id, next_state)

        return ChatResponse(
            session_id=session_id,
            assistant_reply=_public_reply(session_id, next_state),
            state=_public_state(next_state, session_id),
        )

    @server.get("/api/download/{session_id}/pptx")
    def download_pptx(session_id: str) -> FileResponse:
        _, state = store.get_or_create(session_id)
        pptx_path = state.get("pptx_path", "")
        if not pptx_path:
            raise HTTPException(status_code=404, detail="当前会话还没有可下载的 PPT。")

        path = Path(pptx_path)
        if not path.exists() or path.suffix.lower() != ".pptx":
            raise HTTPException(status_code=404, detail="PPT 文件不存在或已被移动。")

        return FileResponse(
            path,
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            filename=path.name,
        )

    return server


def _public_reply(session_id: str, state: State) -> str:
    reply = state.get("assistant_reply", "")
    if state.get("status") != "ppt_exported" or not state.get("pptx_path"):
        if state.get("project_path") and _contains_local_path(reply):
            return _project_ready_reply(state)
        return reply

    return "PPT 已生成，请点击页面中的“下载 PPT”按钮获取文件。"


def _public_state(state: State, session_id: str | None = None) -> dict[str, Any]:
    pptx_ready = bool(state.get("pptx_path"))
    project_ready = bool(state.get("project_path"))
    return {
        "status": state.get("status", "collecting"),
        "requirement": state.get("requirement", {}),
        "requirement_complete": state.get("requirement_complete", False),
        "missing_fields": state.get("missing_fields", []),
        "ppt_brief": state.get("ppt_brief", {}),
        "material": _material_summary(state.get("material", {})),
        "deck_outline": state.get("deck_outline", []),
        "project_path": "",
        "project_ready": project_ready,
        "svg_files": state.get("svg_files", []),
        "pptx_path": "",
        "pptx_ready": pptx_ready,
        "pptx_download_url": _download_url(session_id) if pptx_ready and session_id else "",
        "error": state.get("error", ""),
        "confirmed": state.get("confirmed", False),
    }


def _material_summary(material: dict) -> dict:
    raw_texts = material.get("raw_texts", [])
    return {
        "file_paths": material.get("file_paths", []),
        "topic": material.get("topic", ""),
        "keywords": material.get("keywords", []),
        "key_points": material.get("key_points", []),
        "summary": material.get("summary", {}),
        "raw_text_count": len(raw_texts),
        "raw_texts": raw_texts,
    }


def _download_url(session_id: str) -> str:
    return f"/api/download/{session_id}/pptx"


def _contains_local_path(text: str) -> bool:
    return ":\\" in text or ":/" in text


def _project_ready_reply(state: State) -> str:
    if state.get("status") == "waiting_confirm":
        return '项目资料已创建，请在页面中确认 PPT 制作方案。(回复"确认"开始创建ppt)'

    return "项目资料已创建。"


app = create_app()
