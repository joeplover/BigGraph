"""统一错误码枚举 — 覆盖 200–500 状态码，全中文提示

用法:
    raise ErrorCode.KB_NOT_FOUND.exception()
    raise ErrorCode.FILE_NOT_FOUND.exception(file_id="xxx")
    raise ErrorCode.UPLOAD_FAILED.exception(detail="磁盘空间不足")
"""
from __future__ import annotations

from enum import IntEnum

from fastapi import HTTPException


class ErrorCode(IntEnum):
    """全局错误码枚举

    编码规则: 前三位 = HTTP 状态码, 后三位 = 顺序号
    例如 404001 = HTTP 404, 该分类下第 1 个错误
    """

    # ====================================================================
    # 2xx — 成功（非错误，仅用于标准化响应格式）
    # ====================================================================
    SUCCESS = 200000
    CREATED = 201000
    ACCEPTED = 202000

    # ====================================================================
    # 400 — 请求参数错误
    # ====================================================================
    BAD_REQUEST = 400000
    INVALID_FILE_FORMAT = 400001       # 不支持的文件格式
    MISSING_PARAM = 400002             # 缺少必填参数
    PARAM_VALIDATION_ERROR = 400003    # 参数校验失败
    FILE_TOO_LARGE = 400004            # 文件大小超限
    INVALID_QUERY = 400005             # 搜索查询为空或格式错误

    # ====================================================================
    # 401 — 未授权
    # ====================================================================
    UNAUTHORIZED = 401000
    INVALID_API_KEY = 401001           # API Key 无效
    TOKEN_EXPIRED = 401002             # Token 已过期

    # ====================================================================
    # 403 — 禁止访问
    # ====================================================================
    FORBIDDEN = 403000
    TENANT_MISMATCH = 403001           # 租户 ID 不匹配，无权限操作

    # ====================================================================
    # 404 — 资源不存在
    # ====================================================================
    NOT_FOUND = 404000
    KB_NOT_FOUND = 404001              # 知识库不存在
    DOC_NOT_FOUND = 404002             # 文档不存在
    JOB_NOT_FOUND = 404003             # 导入任务不存在
    FILE_NOT_FOUND = 404004            # 上传文件记录不存在

    # ====================================================================
    # 409 — 资源冲突
    # ====================================================================
    CONFLICT = 409000
    DUPLICATE_FILE = 409001            # 文件重复上传（相同哈希）

    # ====================================================================
    # 422 — 参数语义错误
    # ====================================================================
    UNPROCESSABLE = 422000
    KB_NAME_EMPTY = 422001             # 知识库名称为空

    # ====================================================================
    # 500 — 服务器内部错误
    # ====================================================================
    INTERNAL_ERROR = 500000
    DB_ERROR = 500001                  # 数据库操作异常
    FILE_SAVE_ERROR = 500002           # 文件保存失败
    PARSER_ERROR = 500003              # 文档解析失败
    CHUNK_ERROR = 500004               # 文档切片失败

    # ====================================================================
    # 502 — 上游服务错误
    # ====================================================================
    BAD_GATEWAY = 502000
    EMBEDDING_API_ERROR = 502001       # Embedding 服务调用失败
    QDRANT_ERROR = 502002              # Qdrant 向量库操作失败
    ES_ERROR = 502003                  # Elasticsearch 操作失败

    # ====================================================================
    # 503 — 服务暂不可用
    # ====================================================================
    SERVICE_UNAVAILABLE = 503000
    QDRANT_UNAVAILABLE = 503001        # Qdrant 连接不上
    ES_UNAVAILABLE = 503002            # Elasticsearch 连接不上

    # ====================================================================
    # 方法
    # ====================================================================

    @property
    def http_status(self) -> int:
        """取前三位作为 HTTP 状态码"""
        return self.value // 1000

    @property
    def code(self) -> int:
        """完整错误码（直接用 self.value 也行）"""
        return self.value

    @property
    def default_detail(self) -> str:
        """枚举项自带的默认中文描述"""
        return _DEFAULT_DETAILS.get(self, "未知错误")

    def exception(self, detail: str | None = None, headers: dict | None = None) -> HTTPException:
        """快速构造标准化的 HTTPException"""
        return HTTPException(
            status_code=self.http_status,
            detail=detail or self.default_detail,
            headers=headers,
        )


# =====================================================================
# 默认中文错误提示表
# =====================================================================

_DEFAULT_DETAILS: dict[ErrorCode, str] = {
    # 2xx
    ErrorCode.SUCCESS: "操作成功",
    ErrorCode.CREATED: "创建成功",
    ErrorCode.ACCEPTED: "请求已接受",
    # 400
    ErrorCode.BAD_REQUEST: "请求参数错误",
    ErrorCode.INVALID_FILE_FORMAT: "不支持的文件格式，当前仅支持 txt / md / pdf / docx / csv / xlsx / html",
    ErrorCode.MISSING_PARAM: "缺少必填参数",
    ErrorCode.PARAM_VALIDATION_ERROR: "参数校验失败，请检查输入",
    ErrorCode.FILE_TOO_LARGE: "上传文件大小超过限制",
    ErrorCode.INVALID_QUERY: "搜索查询内容不能为空",
    # 401
    ErrorCode.UNAUTHORIZED: "未授权，请提供有效的认证信息",
    ErrorCode.INVALID_API_KEY: "API Key 无效",
    ErrorCode.TOKEN_EXPIRED: "Token 已过期，请重新获取",
    # 403
    ErrorCode.FORBIDDEN: "禁止访问，无操作权限",
    ErrorCode.TENANT_MISMATCH: "租户不匹配，无权操作该资源",
    # 404
    ErrorCode.NOT_FOUND: "请求的资源不存在",
    ErrorCode.KB_NOT_FOUND: "知识库不存在",
    ErrorCode.DOC_NOT_FOUND: "文档不存在",
    ErrorCode.JOB_NOT_FOUND: "导入任务不存在",
    ErrorCode.FILE_NOT_FOUND: "上传的文件记录不存在",
    # 409
    ErrorCode.CONFLICT: "资源冲突",
    ErrorCode.DUPLICATE_FILE: "文件重复上传，请勿重复提交相同文件",
    # 422
    ErrorCode.UNPROCESSABLE: "请求语义错误",
    ErrorCode.KB_NAME_EMPTY: "知识库名称不能为空",
    # 500
    ErrorCode.INTERNAL_ERROR: "服务器内部错误，请稍后重试",
    ErrorCode.DB_ERROR: "数据库操作异常，请稍后重试",
    ErrorCode.FILE_SAVE_ERROR: "文件保存失败，请检查磁盘空间",
    ErrorCode.PARSER_ERROR: "文档解析失败，请检查文件内容是否损坏",
    ErrorCode.CHUNK_ERROR: "文档切片处理失败",
    # 502
    ErrorCode.BAD_GATEWAY: "上游服务响应异常",
    ErrorCode.EMBEDDING_API_ERROR: "向量模型服务调用失败，请检查 Embedding 服务是否正常运行",
    ErrorCode.QDRANT_ERROR: "向量数据库操作失败，请检查 Qdrant 服务",
    ErrorCode.ES_ERROR: "全文检索引擎操作失败，请检查 Elasticsearch 服务",
    # 503
    ErrorCode.SERVICE_UNAVAILABLE: "服务暂不可用，请稍后重试",
    ErrorCode.QDRANT_UNAVAILABLE: "向量数据库连接失败，请检查 Qdrant 服务状态",
    ErrorCode.ES_UNAVAILABLE: "Elasticsearch 连接失败，请检查 ES 服务状态",
}