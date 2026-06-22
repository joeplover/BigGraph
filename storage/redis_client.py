"""Redis 客户端 — Token 会话存储

结构:
  key:   session:{token_hash_prefix}
  value: {"user_id": "...", "username": "...", "tenant_id": "...", "display_name": "..."}
  TTL:   access_token 的剩余有效期（秒）
"""
from __future__ import annotations

import json
from typing import Optional

import redis as _redis

from config.settings import settings

# ---------------------------------------------------------------------------
# 客户端单例
# ---------------------------------------------------------------------------

_redis_client: Optional[_redis.Redis] = None


def get_redis() -> _redis.Redis:
    """获取 Redis 连接（懒加载单例）"""
    global _redis_client
    if _redis_client is None:
        _redis_client = _redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD or None,
            db=settings.REDIS_DB,
            decode_responses=True,
            socket_timeout=3,
        )
    return _redis_client


# ---------------------------------------------------------------------------
# 会话操作
# ---------------------------------------------------------------------------

_SESSION_PREFIX = "session:"


def save_session(access_token: str, user_info: dict, ttl: int) -> None:
    """将用户会话信息存入 Redis

    Args:
        access_token: JWT access_token（用于派生 key）
        user_info: {"user_id", "username", "tenant_id", "display_name"}
        ttl: 过期时间（秒）
    """
    key = _session_key(access_token)
    r = get_redis()
    r.setex(key, ttl, json.dumps(user_info, ensure_ascii=False))


def get_session(access_token: str) -> dict | None:
    """从 Redis 读取用户会话信息"""
    key = _session_key(access_token)
    r = get_redis()
    data = r.get(key)
    if data is None:
        return None
    return json.loads(data)


def delete_session(access_token: str) -> None:
    """删除会话（登出时调用）"""
    key = _session_key(access_token)
    r = get_redis()
    r.delete(key)


def _session_key(token: str) -> str:
    """用 token 末尾 16 字符作为哈希标识，避免 key 过长"""
    suffix = token[-16:] if len(token) > 16 else token
    return f"{_SESSION_PREFIX}{suffix}"


# ---------------------------------------------------------------------------
# 验证码操作
# ---------------------------------------------------------------------------

_VERIFY_CODE_PREFIX = "verify_code:"


def save_verify_code(email: str, code: str, ttl: int = 300) -> None:
    """保存邮箱验证码（默认 5 分钟有效）

    Args:
        email: 邮箱地址
        code: 验证码
        ttl: 过期时间（秒，默认 300）
    """
    key = f"{_VERIFY_CODE_PREFIX}{email}"
    r = get_redis()
    r.setex(key, ttl, code)


def get_verify_code(email: str) -> str | None:
    """获取邮箱验证码"""
    key = f"{_VERIFY_CODE_PREFIX}{email}"
    r = get_redis()
    return r.get(key)


def delete_verify_code(email: str) -> None:
    """删除邮箱验证码（验证成功后调用）"""
    key = f"{_VERIFY_CODE_PREFIX}{email}"
    r = get_redis()
    r.delete(key)


# ---------------------------------------------------------------------------
# 聊天历史操作
# ---------------------------------------------------------------------------

_CHAT_HISTORY_PREFIX = "chat_history:"
_CHAT_HISTORY_TTL = 86400  # 24 小时


def save_chat_message(session_id: str, role: str, content: str) -> None:
    """保存一条聊天消息到 Redis（追加到列表末尾）

    Args:
        session_id: 会话 ID
        role: "user" 或 "assistant"
        content: 消息内容
    """
    key = f"{_CHAT_HISTORY_PREFIX}{session_id}"
    r = get_redis()
    msg = json.dumps({"role": role, "content": content}, ensure_ascii=False)
    r.rpush(key, msg)
    r.expire(key, _CHAT_HISTORY_TTL)


def get_chat_history(session_id: str, limit: int = 50) -> list[dict]:
    """获取聊天历史（最新的 limit 条）

    Args:
        session_id: 会话 ID
        limit: 最多返回多少条（默认 50）

    Returns:
        [{"role": "user", "content": "..."}, ...]
    """
    key = f"{_CHAT_HISTORY_PREFIX}{session_id}"
    r = get_redis()
    msgs = r.lrange(key, -limit * 2, -1)  # 取最新的 limit*2 条（用户+助手成对）
    return [json.loads(m) for m in msgs]


def clear_chat_history(session_id: str) -> None:
    """清空指定会话的聊天历史"""
    key = f"{_CHAT_HISTORY_PREFIX}{session_id}"
    r = get_redis()
    r.delete(key)


# ---------------------------------------------------------------------------
# 会话元数据
# ---------------------------------------------------------------------------

_CHAT_META_PREFIX = "chat_meta:"
_USER_SESSIONS_PREFIX = "user_sessions:"
_CHAT_TTL = 86400 * 7  # 7 天


def create_chat_session(session_id: str, user_id: str, title: str = "新会话") -> dict:
    """创建新会话，返回会话信息"""
    meta_key = f"{_CHAT_META_PREFIX}{session_id}"
    user_key = f"{_USER_SESSIONS_PREFIX}{user_id}"
    r = get_redis()

    meta = json.dumps({
        "id": session_id,
        "title": title,
        "created_at": __import__("datetime").datetime.now().isoformat(),
        "user_id": user_id,
    }, ensure_ascii=False)
    r.setex(meta_key, _CHAT_TTL, meta)
    r.zadd(user_key, {session_id: __import__("time").time()})
    r.expire(user_key, _CHAT_TTL)
    return json.loads(meta)


def get_chat_session(session_id: str) -> dict | None:
    """Return chat session metadata by id."""
    r = get_redis()
    meta = r.get(f"{_CHAT_META_PREFIX}{session_id}")
    if not meta:
        return None
    return json.loads(meta)


def list_chat_sessions(user_id: str) -> list[dict]:
    """列出用户的所有会话（按时间倒序）"""
    user_key = f"{_USER_SESSIONS_PREFIX}{user_id}"
    r = get_redis()
    session_ids = r.zrevrange(user_key, 0, -1)
    sessions = []
    for sid in session_ids:
        meta_key = f"{_CHAT_META_PREFIX}{sid}"
        meta = r.get(meta_key)
        if meta:
            sessions.append(json.loads(meta))
        else:
            # 元数据过期，清理索引
            r.zrem(user_key, sid)
    return sessions


def rename_chat_session(session_id: str, title: str) -> None:
    """更新会话标题"""
    meta_key = f"{_CHAT_META_PREFIX}{session_id}"
    r = get_redis()
    meta = r.get(meta_key)
    if meta:
        data = json.loads(meta)
        data["title"] = title
        r.setex(meta_key, _CHAT_TTL, json.dumps(data, ensure_ascii=False))


def delete_chat_session(session_id: str, user_id: str) -> None:
    """彻底删除会话（元数据 + 消息 + 索引）"""
    r = get_redis()
    r.delete(f"{_CHAT_META_PREFIX}{session_id}")
    r.delete(f"{_CHAT_HISTORY_PREFIX}{session_id}")
    r.zrem(f"{_USER_SESSIONS_PREFIX}{user_id}", session_id)
