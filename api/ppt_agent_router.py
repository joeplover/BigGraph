"""PPT Agent API 路由 — 低耦合集成 growing_agent

通过 sys.path 导入 ppt_agent 包，不复制代码。

端点:
  POST /api/ppt/chat       — 发送消息给 PPT Agent（同步快速问答 / 异步后台生成）
  GET  /api/ppt/stream/{session_id} — SSE 推送后台任务状态
  GET  /api/ppt/status/{session_id} — 轮询后台任务状态（保底）
  GET  /api/ppt/download/{session_id} — 下载生成的 PPTX 文件
  DEL  /api/ppt/session/{session_id} — 删除 PPT Agent 会话
"""
from __future__ import annotations

import asyncio
import json
import sys
import tempfile
import threading
from pathlib import Path

from fastapi.responses import StreamingResponse

# ---------------------------------------------------------------------------
# 低耦合导入 — 将本项目根加入 sys.path（ppt_agent 已复制到项目根）
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_PROJECT_ROOT_STR = str(_PROJECT_ROOT)
if _PROJECT_ROOT_STR not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT_STR)

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from core.ingestion.registry import ParserRegistry
from core.logging import get_logger
from storage.ppt_state_store import (
    clear_ppt_task_status,
    delete_ppt_state,
    get_ppt_state,
    get_ppt_task_status,
    save_ppt_state,
    save_ppt_task_result,
    save_ppt_task_running,
)
from storage.redis_client import save_chat_message

# 导入 PPT Agent 编译好的 LangGraph
from ppt_agent.graph import app as ppt_graph

logger = get_logger(__name__)

# 全局复用 ParserRegistry（无状态，可安全共享）
_parser_registry = ParserRegistry()

router = APIRouter(prefix="/api/ppt", tags=["PPT Agent"])

# ---------------------------------------------------------------------------
# SSE 事件通知机制
# ---------------------------------------------------------------------------
# 后台线程 → 写入 _ppt_results → 触发 _ppt_events → SSE 端点推送
_ppt_events: dict[str, asyncio.Event] = {}
_ppt_results: dict[str, dict[str, str]] = {}


def _notify_ppt_done(session_id: str, result: dict[str, str]) -> None:
    """后台线程中调用：保存结果并通知 SSE 端点"""
    _ppt_results[session_id] = result
    event = _ppt_events.get(session_id)
    if event:
        event.set()  # 唤醒 SSE 协程


def _cleanup_ppt_event(session_id: str) -> None:
    """清理 SSE 事件（客户端断开或超时）"""
    _ppt_events.pop(session_id, None)
    _ppt_results.pop(session_id, None)


# ---------------------------------------------------------------------------
# 确认词判断
# ---------------------------------------------------------------------------

_CONFIRM_WORDS = frozenset({
    "确认", "同意", "可以", "没问题", "开始", "继续", "ok", "yes", "y",
})

# 用词边界判断：不把"不确认"误判为"确认"
_NEGATIVE_WORDS = frozenset({"不确认", "先不确认", "不同意", "不可以", "有问题"})


def _is_confirmation(text: str) -> bool:
    t = text.strip().lower()
    if t in _CONFIRM_WORDS:
        return True
    if t in _NEGATIVE_WORDS:
        return False
    if "确认" in t and not any(n in t for n in _NEGATIVE_WORDS):
        return True
    return False


def _is_heavy_task(state: dict) -> bool:
    """判断当前 state 是否处于即将进入重任务的阶段"""
    status = state.get("status", "collecting")
    # waiting_confirm 说明用户在确认方案，下一轮确认后就会触发完整的生成管线
    return status in ("waiting_confirm", "confirmed")


# ---------------------------------------------------------------------------
# 请求 / 响应模型
# ---------------------------------------------------------------------------


class PptChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="用户输入")
    session_id: str = Field("", description="PPT Agent 会话 ID")


class PptChatResponse(BaseModel):
    response: str = Field("", description="Assistant 回复")
    session_id: str = Field("", description="会话 ID")
    status: str = Field("collecting", description="当前流程状态")
    pptx_download_url: str = Field("", description="PPTX 下载地址（完成后有值）")
    stream_url: str = Field("", description="SSE 流地址（处理中时有效）")


class PptStatusResponse(BaseModel):
    status: str = Field("idle", description="任务状态: idle/running/done/failed")
    response: str = Field("", description="Assistant 回复")
    pptx_download_url: str = Field("", description="PPTX 下载地址")


# ---------------------------------------------------------------------------
# 后台任务执行
# ---------------------------------------------------------------------------

def _run_ppt_graph_in_background(
    session_id: str,
    state: dict,
    message: str,
) -> None:
    """在后台线程中执行 ppt_graph.invoke()，完成后写入 Redis

    这个函数在独立线程中运行，不阻塞 HTTP 请求。
    """
    logger.info("PPT Agent 后台任务开始: session=%s", session_id)
    try:
        # 将用户消息加入 state
        state.pop("assistant_reply", None)
        state.setdefault("messages", [])
        state["messages"].append(HumanMessage(content=message))

        # 执行完整的 LangGraph
        next_state = ppt_graph.invoke(state)

        # 保存最终的 State
        save_ppt_state(session_id, next_state)

        # 写入聊天历史，支持历史记录加载
        try:
            save_chat_message(session_id, "user", message)
            if reply:
                save_chat_message(session_id, "assistant", reply)
        except Exception:
            pass  # 历史记录写入失败不影响主流程

        # 提取结果
        reply = next_state.get("assistant_reply", "")
        status = next_state.get("status", "collecting")
        pptx_download_url = ""
        if status == "ppt_exported" and next_state.get("pptx_path"):
            pptx_download_url = f"/api/ppt/download/{session_id}"

        save_ppt_task_result(session_id, reply, pptx_download_url, "done")

        # 通知 SSE
        _notify_ppt_done(session_id, {
            "status": "done",
            "response": reply,
            "pptx_download_url": pptx_download_url,
        })

        logger.info(
            "PPT Agent 后台任务完成: session=%s status=%s reply_len=%d",
            session_id, status, len(reply),
        )

    except Exception as exc:
        logger.error("PPT Agent 后台任务失败: session=%s error=%s", session_id, str(exc))
        save_ppt_task_result(session_id, f"PPT 生成失败：{exc}", "", "failed")
        _notify_ppt_done(session_id, {
            "status": "failed",
            "response": f"PPT 生成失败：{exc}",
            "pptx_download_url": "",
        })


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


@router.post("/chat", response_model=PptChatResponse)
def ppt_chat(req: PptChatRequest):
    """发送消息给 PPT Agent

    逻辑：
    - 如果当前处于重任务阶段（用户即将确认方案），启动后台线程异步执行
    - 否则同步执行快速返回
    """
    # 1. 加载或初始化 State
    state = get_ppt_state(req.session_id) if req.session_id else None
    is_new = state is None

    if is_new:
        from ppt_agent.state import State as PptState
        state = dict(PptState(
            messages=[],
            requirement={},
        ))
        session_id = req.session_id or __import__("uuid").uuid4().hex
    else:
        session_id = req.session_id

    # 2. 判断是否走后台任务模式
    if _is_heavy_task(state):
        # 先标记 running
        save_ppt_task_running(session_id)

        # 启动后台线程
        t = threading.Thread(
            target=_run_ppt_graph_in_background,
            args=(session_id, state, req.message),
            daemon=True,
        )
        t.start()

        logger.info("PPT Agent 后台任务已启动: session=%s", session_id)

        return PptChatResponse(
            response="PPT 正在生成中，这可能需要几分钟时间，请耐心等待...",
            session_id=session_id,
            status="processing",
            pptx_download_url="",
            stream_url=f"/api/ppt/stream/{session_id}",
        )

    # 3. 同步模式（快速问答）
    state.pop("assistant_reply", None)
    state.setdefault("messages", [])
    state["messages"].append(HumanMessage(content=req.message))

    logger.info("PPT Agent 同步调用: session=%s msg_len=%d", session_id, len(req.message))
    try:
        next_state = ppt_graph.invoke(state)
    except Exception as exc:
        logger.error("PPT Agent 同步调用失败: session=%s error=%s", session_id, str(exc))
        raise HTTPException(status_code=500, detail=f"PPT Agent 调用失败: {exc}")

    # 保存 State
    save_ppt_state(session_id, next_state)

    # 写入聊天历史，支持历史记录加载
    try:
        save_chat_message(session_id, "user", req.message)
        reply_msg = next_state.get("assistant_reply", "")
        if reply_msg:
            save_chat_message(session_id, "assistant", reply_msg)
    except Exception:
        pass  # 历史记录写入失败不影响主流程

    # 构造响应
    reply = next_state.get("assistant_reply", "")
    status = next_state.get("status", "collecting")

    pptx_download_url = ""
    if status == "ppt_exported" and next_state.get("pptx_path"):
        pptx_download_url = f"/api/ppt/download/{session_id}"

    logger.info(
        "PPT Agent 同步回复: session=%s status=%s reply_len=%d",
        session_id, status, len(reply),
    )

    return PptChatResponse(
        response=reply,
        session_id=session_id,
        status=status,
        pptx_download_url=pptx_download_url,
    )


@router.get("/status/{session_id}", response_model=PptStatusResponse)
def get_ppt_status(session_id: str):
    """轮询 PPT 后台任务状态

    返回: {status: "idle"|"running"|"done"|"failed", response: "...", pptx_download_url: "..."}
    """
    task = get_ppt_task_status(session_id)
    if task is None:
        return PptStatusResponse(status="idle")

    return PptStatusResponse(
        status=task.get("status", "idle"),
        response=task.get("response", ""),
        pptx_download_url=task.get("pptx_download_url", ""),
    )


@router.get("/stream/{session_id}")
async def ppt_stream(session_id: str):
    """SSE 端点 — 实时推送 PPT 生成状态

    后台线程完成工作时，通过 _notify_ppt_done 触发通知，
    本端点立即推送结果给前端。
    """
    async def event_generator():
        # 1. 先检查是否已经有结果了
        result = _ppt_results.get(session_id)
        if result:
            yield f"data: {json.dumps(result, ensure_ascii=False)}\n\n"
            _cleanup_ppt_event(session_id)
            return

        # 2. 检查 Redis 中是否有 task 结果
        task = get_ppt_task_status(session_id)
        if task and task.get("status") in ("done", "failed"):
            yield f"data: {json.dumps(task, ensure_ascii=False)}\n\n"
            return

        # 3. 等待后台任务完成
        event = asyncio.Event()
        _ppt_events[session_id] = event

        try:
            await asyncio.wait_for(event.wait(), timeout=3600)
            result = _ppt_results.pop(session_id, {
                "status": "failed",
                "response": "生成结果丢失",
                "pptx_download_url": "",
            })
            yield f"data: {json.dumps(result, ensure_ascii=False)}\n\n"
        except asyncio.TimeoutError:
            timeout_result = {
                "status": "failed",
                "response": "PPT 生成超时",
                "pptx_download_url": "",
            }
            yield f"data: {json.dumps(timeout_result, ensure_ascii=False)}\n\n"
        finally:
            _cleanup_ppt_event(session_id)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/download/{session_id}")
def download_pptx(session_id: str):
    """下载生成的 PPTX 文件"""
    state = get_ppt_state(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="会话不存在")

    pptx_path = state.get("pptx_path", "")
    if not pptx_path:
        raise HTTPException(status_code=404, detail="当前会话还没有生成的 PPT 文件")

    path = Path(pptx_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="PPT 文件已被移动或删除")

    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename=path.name,
    )


@router.delete("/session/{session_id}")
def delete_ppt_session(session_id: str):
    """删除 PPT Agent 会话状态"""
    delete_ppt_state(session_id)
    clear_ppt_task_status(session_id)
    return {"message": "会话已删除", "session_id": session_id}


# ---------------------------------------------------------------------------
# 文件上传
# ---------------------------------------------------------------------------


@router.post("/upload")
async def upload_ppt_material(
    session_id: str = Form(...),
    file: UploadFile = File(...),
):
    """上传 PPT 素材文件，利用系统解析器提取文本后注入 PPT Agent State

    支持格式: .txt, .md, .pdf, .docx, .csv, .xlsx, .html
    """
    rid = __import__("uuid").uuid4().hex[:12]
    logger.info("PPT 素材上传: name=%s session=%s", file.filename, session_id, extra={"request_id": rid})

    # 1. 加载 PPT Agent State
    state = get_ppt_state(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="PPT Agent 会话不存在，请先发送消息")

    # 2. 保存文件到临时路径（跨平台兼容）
    content = await file.read()
    ext = Path(file.filename).suffix.lower()
    tmp_dir = Path(tempfile.gettempdir())
    tmp_path = tmp_dir / f"ppt_upload_{rid}{ext}"
    try:
        tmp_path.write_bytes(content)
    except Exception as exc:
        logger.error("PPT 素材临时文件写入失败: %s", exc, extra={"request_id": rid})
        raise HTTPException(status_code=500, detail="文件写入失败")

    # 3. 解析文件提取文本
    try:
        parser = _parser_registry.get_parser(tmp_path)
        parsed = parser.parse(tmp_path)
        raw_text = parsed.raw_text
        if not raw_text.strip():
            raise HTTPException(status_code=400, detail="文件内容为空，无法作为 PPT 素材")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("PPT 素材解析失败: %s", exc, extra={"request_id": rid})
        raise HTTPException(status_code=500, detail=f"文件解析失败: {exc}")
    finally:
        # 清理临时文件
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass

    # 4. 注入到 PPT Agent State 的 material 中
    state.setdefault("material", {
        "raw_texts": [],
        "file_paths": [],
        "summary": {},
        "topic": "",
        "keywords": [],
        "key_points": [],
    })
    state["material"]["raw_texts"].append(raw_text)
    state["material"]["file_paths"].append(file.filename or f"uploaded{ext}")

    save_ppt_state(session_id, state)

    text_preview = raw_text[:100].replace("\n", " ") + ("..." if len(raw_text) > 100 else "")
    logger.info(
        "PPT 素材上传成功: name=%s text_len=%d preview=%s",
        file.filename, len(raw_text), text_preview,
        extra={"request_id": rid},
    )

    return {
        "filename": file.filename,
        "text_length": len(raw_text),
        "message": f"✅ {file.filename} 已上传，共 {len(raw_text)} 字，可作为 PPT 素材使用",
    }