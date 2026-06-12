"""RAG 知识库操作工具集 — 供 LLM Agent 调用

所有工具封装为函数，可直接 binding 到 ChatOpenAI 的 tools 参数。
后端 API 地址统一从全局配置读取。
"""
from __future__ import annotations

import httpx
from typing import Optional

from config.settings import settings

# ---------------------------------------------------------------------------
# 基础客户端
# ---------------------------------------------------------------------------

_BASE_URL = "http://localhost:8000"
_TIMEOUT = httpx.Timeout(60.0, connect=10.0)


def _build_client() -> httpx.Client:
    return httpx.Client(base_url=_BASE_URL, timeout=_TIMEOUT)


# ===================================================================
#  知识库
# ===================================================================


def create_knowledge_base(
    tenant_id: str,
    name: str,
    description: str = "",
) -> dict:
    """创建一个新的知识库（向量知识库，用于上传文档并支持语义检索）。

    Args:
        tenant_id: 租户 ID（必填，例如 "default"）
        name: 知识库名称（必填）
        description: 知识库描述（可选）

    Returns:
        包含 id / name / tenant_id 的知识库信息
    """
    with _build_client() as client:
        resp = client.post(
            "/knowledge_bases/",
            params={"tenant_id": tenant_id, "name": name, "description": description},
        )
        resp.raise_for_status()
        return resp.json()


def get_knowledge_base(kb_id: str) -> dict:
    """根据 ID 获取知识库详细信息。

    Args:
        kb_id: 知识库 ID

    Returns:
        知识库完整信息（名称、租户、创建时间等）
    """
    with _build_client() as client:
        resp = client.get(f"/knowledge_bases/{kb_id}")
        resp.raise_for_status()
        return resp.json()


# ===================================================================
#  文件上传与处理
# ===================================================================


def upload_file(
    kb_id: str,
    file_path: str,
    tenant_id: str = "default",
) -> dict:
    """上传文档文件到指定知识库，触发后台解析 → 切片 → 向量化流水线。

    Args:
        kb_id: 目标知识库 ID
        file_path: 本地文件路径（支持 PDF / Word / Markdown / 文本等格式）
        tenant_id: 租户 ID（默认 "default"）

    Returns:
        包含 job_id / file_id / file_name / status 的处理信息
    """
    with open(file_path, "rb") as f:
        files = {"file": (file_path.split("/")[-1], f, "application/octet-stream")}
        with _build_client() as client:
            resp = client.post(
                f"/upload/{kb_id}",
                data={"tenant_id": tenant_id},
                files=files,
            )
            resp.raise_for_status()
            return resp.json()


def get_job_status(job_id: str) -> dict:
    """查询文件导入任务的后台处理状态。

    状态流转: pending → parsing → cleaning → chunking → embedding → completed / failed

    Args:
        job_id: 导入任务 ID（上传文件时返回）

    Returns:
        包含当前 status / progress / error_message 的任务状态信息
    """
    with _build_client() as client:
        resp = client.get(f"/jobs/{job_id}")
        resp.raise_for_status()
        return resp.json()


# ===================================================================
#  文档查询
# ===================================================================


def get_document(doc_id: str) -> dict:
    """获取已导入文档的元数据信息。

    Args:
        doc_id: 文档 ID

    Returns:
        文档的标题、状态、类型、版本、解析器等元数据
    """
    with _build_client() as client:
        resp = client.get(f"/documents/{doc_id}")
        resp.raise_for_status()
        return resp.json()


def search_documents(
    kb_id: str,
    query: str,
    limit: int = 10,
    tenant_id: str = "default",
) -> dict:
    """在指定知识库中执行向量语义搜索，找到与 query 最相关的文档片段。

    使用 Qdrant 向量检索 + Elasticsearch 全文补充的混合检索方式。

    Args:
        kb_id: 知识库 ID
        query: 搜索查询文本（必填）
        limit: 返回结果数量上限（默认 10）
        tenant_id: 租户 ID（默认 "default"）

    Returns:
        包含 results 列表（每个结果含 chunk_id / content / score / heading_path 等）的搜索结果
    """
    with _build_client() as client:
        resp = client.get(
            f"/search/{kb_id}",
            params={"query": query, "limit": limit, "tenant_id": tenant_id},
        )
        resp.raise_for_status()
        return resp.json()


# ===================================================================
#  文档删除
# ===================================================================


def delete_document(doc_id: str) -> dict:
    """删除文档及其关联的所有数据（PostgreSQL 软删除 + Qdrant 向量删除 + Elasticsearch 删除）。

    Args:
        doc_id: 文档 ID

    Returns:
        删除结果信息（包含 deleted_chunks 数量）
    """
    with _build_client() as client:
        resp = client.delete(f"/documents/{doc_id}")
        resp.raise_for_status()
        return resp.json()


# ===================================================================
#  快捷：搜索并将结果格式化为上下文字符串（供 LLM 拼接 prompt 使用）
# ===================================================================


def search_as_context(
    kb_id: str,
    query: str,
    limit: int = 5,
    tenant_id: str = "default",
) -> str:
    """搜索知识库并将结果格式化为可读的上下文字符串，适合拼接到 LLM prompt 中。

    Args:
        kb_id: 知识库 ID
        query: 搜索关键词
        limit: 返回片段数（默认 5）
        tenant_id: 租户 ID（默认 "default"）

    Returns:
        格式化的参考上下文文本
    """
    result = search_documents(kb_id=kb_id, query=query, limit=limit, tenant_id=tenant_id)
    items = result.get("results", [])
    if not items:
        return "未找到相关文档内容。"

    lines = ["以下是检索到的相关文档片段（按相关性排序）：\n"]
    for i, item in enumerate(items, 1):
        source = item.get("file_name") or f"文档 {item.get('document_id', '')}"
        heading = item.get("heading_path") or ""
        score = item.get("score", 0)
        content = item.get("content", "")
        lines.append(f"--- {i}. [{source}] 相关度={score:.3f} {'| ' + heading if heading else ''}")
        lines.append(content)
        lines.append("")
    return "\n".join(lines)


# ===================================================================
#  权限校验工具（Graph 节点中直接调 Postgres 版见 ChatNode.py）
# ===================================================================


def check_user_kb_access(user_id: str, kb_id: str) -> bool:
    """检查用户是否有权限访问该知识库（直接查 PG，供 Graph 调用）

    Args:
        user_id: 用户 UUID
        kb_id: 知识库 UUID

    Returns:
        True=有权限, False=无权限
    """
    from storage.postgres import KbMemberStore, KnowledgeBaseStore, get_session

    with get_session() as db:
        kb = KnowledgeBaseStore.get(db, kb_id)
        if not kb:
            return False
        if str(kb.owner_id) == user_id:
            return True
        return KbMemberStore.user_can_access(db, user_id, kb_id)