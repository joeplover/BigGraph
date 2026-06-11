"""统一日志配置 — 控制台 + 按天滚动文件，支持 request_id 追踪

用法:
    from core.logging import get_logger

    logger = get_logger(__name__)
    logger.info("消息", extra={"request_id": "xxx"})

在 FastAPI 中通过中间件自动注入 request_id：
    from core.logging import RequestIDMiddleware
    app.add_middleware(RequestIDMiddleware)
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any

from config.settings import settings

# ---------------------------------------------------------------------------
# 日志格式
# ---------------------------------------------------------------------------

_LOG_FORMAT = (
    "[%(asctime)s] [%(levelname)-5s] [%(name)-25s] "
    "[%(request_id)s] %(message)s"
)
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


# ---------------------------------------------------------------------------
# 自定义 Formatter — 保证 request_id 有默认值
# ---------------------------------------------------------------------------

class _RequestIDFormatter(logging.Formatter):
    """如果 record 没有 request_id 属性，补默认值 '-'"""

    def format(self, record: logging.LogRecord) -> str:
        if not hasattr(record, "request_id"):
            record.request_id = "-"          # type: ignore[attr-defined]
        return super().format(record)


# ---------------------------------------------------------------------------
# 全局 Handler 安装（只执行一次）
# ---------------------------------------------------------------------------

_initialized = False


def _ensure_handlers() -> None:
    """安装控制台 Handler + 文件 Handler（幂等）"""
    global _initialized
    if _initialized:
        return
    _initialized = True

    root = logging.getLogger()
    root.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

    fmt = _RequestIDFormatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    # —— 控制台 Handler ——
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.DEBUG)
    console.setFormatter(fmt)
    root.addHandler(console)

    # —— 文件 Handler（按天滚动，保留 30 天） ——
    log_dir = Path(settings.LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = str(log_dir / "biggraph.log")

    file_handler = TimedRotatingFileHandler(
        log_file,
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)


# ---------------------------------------------------------------------------
# 公开 API
# ---------------------------------------------------------------------------

def get_logger(name: str | None = None) -> logging.Logger:
    """获取带模块名的 Logger，自动初始化日志系统"""
    _ensure_handlers()
    return logging.getLogger(name or __name__)


def make_request_id() -> str:
    """生成短 request_id，适合日志追踪"""
    import uuid
    return uuid.uuid4().hex[:12]


# ===================================================================
# FastAPI 中间件 — 自动注入 request_id
# ===================================================================

class RequestIDMiddleware:
    """为每个请求注入 request_id 到 request.state 和日志上下文。

    用法:
        from core.logging import RequestIDMiddleware
        app.add_middleware(RequestIDMiddleware)
    """

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        from uuid import uuid4 as _uuid4
        request_id = _uuid4().hex[:12]

        # 塞进 scope，路由处理时可通过 request.scope["request_id"] 读取
        scope["request_id"] = request_id

        # 包装 send 以记录响应日志（可选）
        logger = get_logger("http")

        async def log_send(message: Any) -> None:
            if message["type"] == "http.response.start":
                status = message.get("status", 0)
                logger.info(
                    "%s %s → %s",
                    scope.get("method", "?"),
                    scope.get("path", "?"),
                    status,
                    extra={"request_id": request_id},
                )
            await send(message)

        await self.app(scope, receive, log_send)
