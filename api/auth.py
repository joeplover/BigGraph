"""认证模块 — 用户注册 / 登录 / Token 刷新 / 当前用户

所有密码使用 passlib + bcrypt 哈希，会话存 Redis。
错误码统一使用 ErrorCode 枚举，日志遵循系统格式。
"""
from __future__ import annotations

import bcrypt
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from api.mail_service import send_verify_code
from core.auth.jwt import (
    create_token_pair,
    verify_token,
)
from core.logging import get_logger, make_request_id
from storage.error_codes import ErrorCode
from storage.postgres import UserStore, get_session
from storage.redis_client import (
    save_session,
    get_session as redis_get_session,
    delete_session,
    get_verify_code,
    delete_verify_code,
)

# ---------------------------------------------------------------------------
# Router & Logger
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/auth", tags=["认证"])
logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# 请求 / 响应模型
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=50, description="用户名")
    password: str = Field(..., min_length=6, max_length=128, description="密码")
    display_name: str | None = Field(None, max_length=100, description="显示名称")
    email: str = Field(..., description="邮箱")
    code: str = Field(..., min_length=6, max_length=6, description="邮箱验证码")


class LoginRequest(BaseModel):
    account: str = Field(..., description="用户名或邮箱")
    password: str = Field(..., description="密码")


class SendCodeRequest(BaseModel):
    email: str = Field(..., description="邮箱地址")


class UserInfoResponse(BaseModel):
    user_id: str
    username: str
    display_name: str | None
    email: str | None
    tenant_id: str
    created_at: str | None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserInfoResponse


# ---------------------------------------------------------------------------
# 依赖：获取当前用户（从请求头解析 token）
# ---------------------------------------------------------------------------

def _get_token_from_header(authorization: str = Header(..., description="Bearer <token>")) -> str:
    """从 Authorization 头提取 access_token"""
    if not authorization.lower().startswith("bearer "):
        rid = make_request_id()
        logger.warning("认证头格式错误: %s...", authorization[:20], extra={"request_id": rid})
        raise ErrorCode.UNAUTHORIZED.exception(detail="认证头格式错误，应为: Bearer <token>")
    return authorization[7:]


def get_current_user(authorization: str = Depends(_get_token_from_header)) -> dict:
    """验证 access_token 并返回用户信息（供 API 路由注入）"""
    rid = make_request_id()

    # 1. JWT 验证
    payload = verify_token(authorization, expected_type="access")
    if payload is None:
        logger.warning("Token 无效或已过期", extra={"request_id": rid})
        raise ErrorCode.TOKEN_EXPIRED.exception()

    # 2. Redis 会话验证
    session = redis_get_session(authorization)
    if session is None:
        logger.warning("Redis 会话不存在: user_id=%s", payload.get("user_id"), extra={"request_id": rid})
        raise ErrorCode.TOKEN_EXPIRED.exception(detail="会话不存在或已过期，请重新登录")

    return session


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


@router.post("/send-code")
def send_code(req: SendCodeRequest):
    """发送邮箱验证码"""
    rid = make_request_id()

    # 检查邮件是否已注册
    with get_session() as db:
        existing = UserStore.get_by_email(db, req.email)
        if existing:
            logger.warning("邮箱已注册: %s", req.email, extra={"request_id": rid})
            raise ErrorCode.CONFLICT.exception(detail="该邮箱已被注册")

    try:
        send_verify_code(req.email)
        logger.info("验证码已发送: email=%s", req.email, extra={"request_id": rid})
        return {"message": "验证码已发送，请查收邮箱", "email": req.email}
    except Exception:
        raise ErrorCode.INTERNAL_ERROR.exception(detail="验证码发送失败，请检查邮箱地址或稍后重试")


@router.post("/register", response_model=TokenResponse)
def register(req: RegisterRequest):
    """用户注册 — 邮箱验证码校验 → 创建用户 → 自动登录返回双 Token"""
    rid = make_request_id()

    # 校验验证码
    saved_code = get_verify_code(req.email)
    if saved_code is None:
        logger.warning("注册失败，验证码已过期: email=%s", req.email, extra={"request_id": rid})
        raise ErrorCode.BAD_REQUEST.exception(detail="验证码已过期，请重新获取")
    if saved_code != req.code:
        logger.warning("注册失败，验证码错误: email=%s", req.email, extra={"request_id": rid})
        raise ErrorCode.BAD_REQUEST.exception(detail="验证码错误")

    with get_session() as db:
        existing = UserStore.get_by_username(db, req.username)
        if existing:
            logger.warning("注册失败，用户名已存在: %s", req.username, extra={"request_id": rid})
            raise ErrorCode.CONFLICT.exception(detail="用户名已存在")

        existing_email = UserStore.get_by_email(db, req.email)
        if existing_email:
            logger.warning("注册失败，邮箱已存在: %s", req.email, extra={"request_id": rid})
            raise ErrorCode.CONFLICT.exception(detail="该邮箱已被注册")

        # 密码哈希
        password_hash = bcrypt.hashpw(req.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        # 创建用户（带邮箱）
        user = UserStore.create(
            db,
            username=req.username,
            password_hash=password_hash,
            display_name=req.display_name or req.username,
            email=req.email,
        )

        user_id = str(user.id)
        username = user.username
        tenant_id = user.tenant_id
        display_name = user.display_name
        email = user.email
        created_at = user.created_at

    # 删除已使用的验证码
    delete_verify_code(req.email)

    # 签发双 Token
    tokens = create_token_pair(user_id, username, tenant_id)

    # 写入 Redis 会话
    save_session(
        tokens["access_token"],
        {"user_id": user_id, "username": username, "tenant_id": tenant_id, "display_name": display_name},
        ttl=3600,
    )

    logger.info("用户注册成功: username=%s email=%s user_id=%s tenant=%s",
                 username, email, user_id, tenant_id, extra={"request_id": rid})

    return TokenResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        user=UserInfoResponse(
            user_id=user_id,
            username=username,
            display_name=display_name,
            email=email,
            tenant_id=tenant_id,
            created_at=created_at.isoformat() if created_at else None,
        ),
    )


@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest):
    """用户登录 — 支持用户名或邮箱"""
    rid = make_request_id()

    with get_session() as db:
        user = UserStore.get_by_username_or_email(db, req.account)
        if not user:
            logger.warning("登录失败，用户不存在: %s", req.account, extra={"request_id": rid})
            raise ErrorCode.UNAUTHORIZED.exception(detail="用户名/邮箱或密码错误")

        if not user.is_active:
            logger.warning("登录失败，账户已禁用: %s", req.account, extra={"request_id": rid})
            raise ErrorCode.FORBIDDEN.exception(detail="账户已被禁用")

        if not bcrypt.checkpw(req.password.encode("utf-8"), user.password_hash.encode("utf-8")):
            logger.warning("登录失败，密码错误: %s", req.account, extra={"request_id": rid})
            raise ErrorCode.UNAUTHORIZED.exception(detail="用户名/邮箱或密码错误")

        user_id = str(user.id)
        username = user.username
        tenant_id = user.tenant_id
        display_name = user.display_name
        email = user.email
        created_at = user.created_at

    # 签发双 Token
    tokens = create_token_pair(user_id, username, tenant_id)

    # 写入 Redis 会话
    save_session(
        tokens["access_token"],
        {"user_id": user_id, "username": username, "tenant_id": tenant_id, "display_name": display_name},
        ttl=3600,
    )

    logger.info("用户登录成功: username=%s user_id=%s tenant=%s",
                 username, user_id, tenant_id, extra={"request_id": rid})

    return TokenResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        user=UserInfoResponse(
            user_id=user_id,
            username=username,
            display_name=display_name,
            email=email,
            tenant_id=tenant_id,
            created_at=created_at.isoformat() if created_at else None,
        ),
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(refresh_token: str = Header(..., alias="X-Refresh-Token", description="refresh_token")):
    """刷新 access_token — 使用 refresh_token 换取新的双 Token"""
    rid = make_request_id()

    payload = verify_token(refresh_token, expected_type="refresh")
    if payload is None:
        logger.warning("Refresh Token 无效或已过期", extra={"request_id": rid})
        raise ErrorCode.TOKEN_EXPIRED.exception(detail="Refresh Token 无效或已过期")

    user_id = payload["user_id"]
    username = payload["username"]
    tenant_id = payload["tenant_id"]

    # 签发新 Token 对
    tokens = create_token_pair(user_id, username, tenant_id)

    # 更新 Redis 会话
    save_session(
        tokens["access_token"],
        {"user_id": user_id, "username": username, "tenant_id": tenant_id, "display_name": username},
        ttl=3600,
    )

    logger.info("Token 刷新成功: user_id=%s", user_id, extra={"request_id": rid})

    return TokenResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        user=UserInfoResponse(
            user_id=user_id,
            username=username,
            display_name=username,
            tenant_id=tenant_id,
            created_at=None,
        ),
    )


@router.get("/me", response_model=UserInfoResponse)
def me(user: dict = Depends(get_current_user)):
    """获取当前用户信息"""
    rid = make_request_id()
    logger.info("查询当前用户信息: user_id=%s", user["user_id"], extra={"request_id": rid})
    return UserInfoResponse(
        user_id=user["user_id"],
        username=user["username"],
        display_name=user.get("display_name"),
        email=user.get("email"),
        tenant_id=user["tenant_id"],
        created_at=None,
    )


@router.post("/logout")
def logout(authorization: str = Depends(_get_token_from_header)):
    """登出 — 删除 Redis 中的会话"""
    rid = make_request_id()
    delete_session(authorization)
    logger.info("用户登出成功", extra={"request_id": rid})
    return {"message": "已退出登录"}