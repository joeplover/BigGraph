from __future__ import annotations

from storage.error_codes import ErrorCode
from storage.redis_client import get_chat_session


def require_chat_session_owner(session_id: str, user: dict) -> dict:
    session = get_chat_session(session_id)
    if not session:
        raise ErrorCode.NOT_FOUND.exception(detail="Chat session not found")
    if str(session.get("user_id")) != str(user["user_id"]):
        raise ErrorCode.FORBIDDEN.exception(detail="You do not have access to this chat session")
    return session
