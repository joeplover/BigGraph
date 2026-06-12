"""PPT Agent 状态存储 — 基于 Redis

将 PPT Agent 的 LangGraph State 整体存入 Redis，
与聊天历史分离，互不干扰。

Key 格式:
  ppt_state:{session_id}       — LangGraph State dict (JSON)
  ppt_task:{session_id}        — 后台任务状态 (JSON)

PPT State TTL: 7 天
PPT Task TTL:  1 小时（生成完成后保留足够时间供前端轮询 + 下载）
"""
from __future__ import annotations

import json
from typing import Any

from storage.redis_client import get_redis

_PPT_STATE_PREFIX = "ppt_state:"
_PPT_STATE_TTL = 86400 * 7  # 7 天

_PPT_TASK_PREFIX = "ppt_task:"
_PPT_TASK_TTL = 3600  # 1 小时


# ===================================================================
#  PPT LangGraph State 操作
# ===================================================================


def get_ppt_state(session_id: str) -> dict[str, Any] | None:
    """从 Redis 读取 PPT Agent 状态

    Args:
        session_id: 会话 ID

    Returns:
        State dict，不存在时返回 None
    """
    key = f"{_PPT_STATE_PREFIX}{session_id}"
    r = get_redis()
    data = r.get(key)
    if data is None:
        return None
    return json.loads(data)


def save_ppt_state(session_id: str, state: dict[str, Any]) -> None:
    """将 PPT Agent 状态存入 Redis

    Args:
        session_id: 会话 ID
        state: LangGraph State dict
    """
    key = f"{_PPT_STATE_PREFIX}{session_id}"
    r = get_redis()
    r.setex(key, _PPT_STATE_TTL, json.dumps(state, ensure_ascii=False, default=str))


def delete_ppt_state(session_id: str) -> None:
    """删除 PPT Agent 状态

    Args:
        session_id: 会话 ID
    """
    key = f"{_PPT_STATE_PREFIX}{session_id}"
    r = get_redis()
    r.delete(key)


# ===================================================================
#  PPT 后台任务状态操作
# ===================================================================


def save_ppt_task_running(session_id: str, message: str = "PPT 正在生成中，请稍候...") -> None:
    """标记 PPT 后台任务为 running

    Args:
        session_id: 会话 ID
        message: 给用户的提示文本
    """
    key = f"{_PPT_TASK_PREFIX}{session_id}"
    r = get_redis()
    r.setex(
        key, _PPT_TASK_TTL,
        json.dumps({"status": "running", "response": message, "pptx_download_url": ""}, ensure_ascii=False),
    )


def save_ppt_task_result(
    session_id: str,
    response: str,
    pptx_download_url: str = "",
    status: str = "done",
) -> None:
    """保存 PPT 后台任务完成结果

    Args:
        session_id: 会话 ID
        response: 给用户的回复
        pptx_download_url: PPTX 下载链接
        status: "done" 或 "failed"
    """
    key = f"{_PPT_TASK_PREFIX}{session_id}"
    r = get_redis()
    r.setex(
        key, _PPT_TASK_TTL,
        json.dumps({
            "status": status,
            "response": response,
            "pptx_download_url": pptx_download_url,
        }, ensure_ascii=False),
    )


def get_ppt_task_status(session_id: str) -> dict[str, Any] | None:
    """获取 PPT 后台任务状态

    Args:
        session_id: 会话 ID

    Returns:
        {"status": "running"|"done"|"failed", "response": "...", "pptx_download_url": "..."}
        任务不存在时返回 None
    """
    key = f"{_PPT_TASK_PREFIX}{session_id}"
    r = get_redis()
    data = r.get(key)
    if data is None:
        return None
    return json.loads(data)


def clear_ppt_task_status(session_id: str) -> None:
    """清除 PPT 后台任务状态

    Args:
        session_id: 会话 ID
    """
    key = f"{_PPT_TASK_PREFIX}{session_id}"
    r = get_redis()
    r.delete(key)