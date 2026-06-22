"""邮箱服务 — 通过 Resend API 发送验证码

无需开通 SMTP 服务，注册 Resend 获取 API key 即可使用。
免费额度 100 封/天，支持任意邮箱地址。
"""
from __future__ import annotations

import random

import requests

from config.settings import settings
from core.logging import get_logger
from storage.redis_client import save_verify_code

logger = get_logger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"


def _generate_code(length: int = 6) -> str:
    """生成数字验证码"""
    return "".join(str(random.randint(0, 9)) for _ in range(length))


def send_verify_code(email: str) -> str:
    """通过 Resend API 发送邮箱验证码

    Args:
        email: 目标邮箱

    Returns:
        验证码字符串
    """
    code = _generate_code()

    response = requests.post(
        RESEND_API_URL,
        headers={
            "Authorization": f"Bearer {settings.RESEND_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "from": settings.RESEND_FROM_EMAIL,
            "to": [email],
            "subject": "BigGraph 注册验证码",
            "text": f"您的验证码为：{code}\n\n验证码有效期为 5 分钟，请尽快完成注册。\n如果不是您本人操作，请忽略此邮件。\n\n—— BigGraph 团队",
        },
        timeout=15,
    )

    if response.status_code not in (200, 201):
        logger.error("Resend 发送失败: status=%s body=%s", response.status_code, response.text)
        raise RuntimeError(f"邮件发送失败 (HTTP {response.status_code})")

    logger.info("验证码已通过 Resend 发送: email=%s", email)

    # 存入 Redis（5 分钟有效）
    save_verify_code(email, code, ttl=300)

    return code