"""邮箱服务 — 发送验证码

使用 SMTP 发送邮件，配置从 settings 读取。
"""
from __future__ import annotations

import random
import smtplib
from email.mime.text import MIMEText

from config.settings import settings
from core.logging import get_logger
from storage.redis_client import save_verify_code

logger = get_logger(__name__)


def _generate_code(length: int = 6) -> str:
    """生成数字验证码"""
    return "".join(str(random.randint(0, 9)) for _ in range(length))


def send_verify_code(email: str) -> str:
    """生成并发送邮箱验证码

    Args:
        email: 目标邮箱

    Returns:
        验证码字符串（用于后续校验）
    """
    code = _generate_code()

    # 构建邮件
    subject = "BigGraph 注册验证码"
    body = f"""您的验证码为：{code}

验证码有效期为 5 分钟，请尽快完成注册。
如果不是您本人操作，请忽略此邮件。

—— BigGraph 团队
"""
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_USER
    msg["To"] = email

    try:
        if settings.SMTP_USE_SSL:
            with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.SMTP_USER, [email], msg.as_string())
        else:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
                server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.SMTP_USER, [email], msg.as_string())

        logger.info("验证码已发送: email=%s", email)
    except smtplib.SMTPAuthenticationError:
        logger.error("SMTP 认证失败，请检查邮箱账号和授权码: email=%s", settings.SMTP_USER)
        raise
    except smtplib.SMTPException as e:
        logger.error("SMTP 发送失败: %s", str(e))
        raise

    # 存入 Redis（5 分钟有效）
    save_verify_code(email, code, ttl=300)

    return code