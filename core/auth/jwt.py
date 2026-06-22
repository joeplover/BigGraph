"""JWT 令牌工具 — 签发 / 验证 / 刷新

使用 PyJWT 库，支持 access_token 和 refresh_token。
"""
from datetime import datetime, timedelta, timezone

import jwt

from config.settings import settings

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

_ALGORITHM = "HS256"


def _secret_key() -> str:
    return settings.JWT_SECRET_KEY


def _access_token_expire() -> timedelta:
    return timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)


def _refresh_token_expire() -> timedelta:
    return timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)


# ---------------------------------------------------------------------------
# 令牌载荷类型
# ---------------------------------------------------------------------------

class TokenPayload:
    """JWT 载荷的字段约定"""
    user_id: str
    username: str
    tenant_id: str
    token_type: str  # "access" | "refresh"


# ---------------------------------------------------------------------------
# 签发
# ---------------------------------------------------------------------------

def create_access_token(user_id: str, username: str, tenant_id: str) -> str:
    """签发 access_token（有效期 1 小时）"""
    now = datetime.now(timezone.utc)
    payload = {
        "user_id": user_id,
        "username": username,
        "tenant_id": tenant_id,
        "token_type": "access",
        "iat": now,
        "exp": now + _access_token_expire(),
    }
    return jwt.encode(payload, _secret_key(), algorithm=_ALGORITHM)


def create_refresh_token(user_id: str, username: str, tenant_id: str) -> str:
    """签发 refresh_token（有效期 7 天）"""
    now = datetime.now(timezone.utc)
    payload = {
        "user_id": user_id,
        "username": username,
        "tenant_id": tenant_id,
        "token_type": "refresh",
        "iat": now,
        "exp": now + _refresh_token_expire(),
    }
    return jwt.encode(payload, _secret_key(), algorithm=_ALGORITHM)


def create_token_pair(user_id: str, username: str, tenant_id: str) -> dict:
    """签发双 Token"""
    return {
        "access_token": create_access_token(user_id, username, tenant_id),
        "refresh_token": create_refresh_token(user_id, username, tenant_id),
        "token_type": "bearer",
    }


# ---------------------------------------------------------------------------
# 验证
# ---------------------------------------------------------------------------

def verify_token(token: str, expected_type: str | None = "access") -> dict | None:
    """验证 JWT 并返回 payload，失败返回 None"""
    try:
        payload = jwt.decode(token, _secret_key(), algorithms=[_ALGORITHM])
        if expected_type and payload.get("token_type") != expected_type:
            return None
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
