"""文档知识库管理系统 — FastAPI 控制器

负责:
  - 知识库 CRUD（创建 / 查询 / 分享 / 成员管理）
  - 文件上传 & 后台处理流水线
  - 向量索引（Qdrant）+ 全文索引（Elasticsearch）
  - 混合检索
  - 文档删除（PG + 向量库联动）
  - JWT 认证保护
"""
from __future__ import annotations

import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中（支持 python xxx.py 直接运行）
_bg_root = Path(__file__).resolve().parent.parent
if str(_bg_root) not in sys.path:
    sys.path.insert(0, str(_bg_root))

import asyncio
import hashlib
import secrets
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile, Depends
from pydantic import BaseModel, Field

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from api.auth import get_current_user, router as auth_router
from config.settings import settings
from core.ingestion.chunker import StructureAwareChunker
from core.ingestion.parser_base import Chunk
from core.ingestion.registry import ParserRegistry
from core.logging import RequestIDMiddleware, get_logger, make_request_id
from storage.elasticsearch import ElasticsearchService
from storage.error_codes import ErrorCode
from storage.models import (
    DocumentChunk,
    DocumentStatus,
    IngestionJobStatus,
    KbMemberRole,
    KbMemberStatus,
    QdrantChunkModel,
    VectorSyncStatus,
)
from storage.postgres import (
    DocumentChunkStore,
    DocumentStore,
    IngestionJobStore,
    KbMemberStore,
    KnowledgeBaseStore,
    UploadedFileStore,
    get_session,
    init_db,
)
from graphs.RAG_Chat_Graph.LLM import llm as chat_llm
from storage.qdrant import QdrantService
from storage.redis_client import (
    create_chat_session,
    delete_chat_session,
    get_chat_history,
    list_chat_sessions,
    rename_chat_session,
    save_chat_message,
)

# ---------------------------------------------------------------------------
# FastAPI 应用
# ---------------------------------------------------------------------------

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """应用生命周期 — 启动时建表"""
    init_db()
    logger.info("数据库表已就绪")
    yield


app = FastAPI(title="文档知识库管理系统", version="1.0.0", lifespan=lifespan)
app.add_middleware(RequestIDMiddleware)


# ---------------------------------------------------------------------------
# 时间工具
# ---------------------------------------------------------------------------


def _local_iso(dt: datetime | None) -> str | None:
    """格式化时间，格式: 2026-06-11 15:11:16"""
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------------------
# 全局异常处理器 — 统一错误响应格式
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """兜底处理器：将未捕获的异常转为标准错误响应"""
    from fastapi.responses import JSONResponse

    rid = request.scope.get("request_id", "-")
    if isinstance(exc, HTTPException):
        logger.warning(
            "HTTP %d: %s", exc.status_code, exc.detail,
            extra={"request_id": rid},
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.status_code * 1000,
                "message": exc.detail,
            },
        )
    # 非 HTTPException 的统一兜底
    logger.error(
        "未捕获异常: %s", str(exc),
        extra={"request_id": rid},
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "code": ErrorCode.INTERNAL_ERROR,
            "message": ErrorCode.INTERNAL_ERROR.default_detail,
        },
    )

# 全局复用（无状态客户端，可安全共享）
_parser_registry = ParserRegistry()
_chunker = StructureAwareChunker()
_qdrant = QdrantService()
_es = ElasticsearchService()


# ===================================================================
#  知识库
# ===================================================================

@app.get("/knowledge_bases/")
async def list_my_knowledge_bases(user: dict = Depends(get_current_user)):
    """获取当前用户有权限访问的知识库列表（自己的 + 已加入的）"""
    rid = make_request_id()
    user_id = user["user_id"]
    tenant_id = user["tenant_id"]

    with get_session() as db:
        # 1. 自己创建的知识库
        owned = KnowledgeBaseStore.list_by_owner(db, user_id)
        # 2. 已加入的知识库
        approved_members = KbMemberStore.list_approved_by_user(db, user_id)
        joined_ids = [str(m.knowledge_base_id) for m in approved_members]
        joined = [KnowledgeBaseStore.get(db, jid) for jid in joined_ids]
        joined = [kb for kb in joined if kb and str(kb.owner_id) != user_id]

        result = []
        seen = set()
        for kb in owned + joined:
            if kb and kb.id not in seen:
                seen.add(kb.id)
                result.append({
                    "id": str(kb.id),
                    "name": kb.name,
                    "description": kb.description,
                    "tenant_id": kb.tenant_id,
                    "owner_id": str(kb.owner_id) if kb.owner_id else None,
                    "is_owner": str(kb.owner_id) == user_id,
                    "created_at": _local_iso(kb.created_at),
                })

        logger.info("知识库列表: user=%s count=%d", user_id, len(result), extra={"request_id": rid})
        return result


@app.post("/knowledge_bases/")
async def create_knowledge_base(name: str, description: str = "",
                                user: dict = Depends(get_current_user)):
    """创建知识库（需认证）"""
    rid = make_request_id()
    tenant_id = user["tenant_id"]
    user_id = user["user_id"]
    with get_session() as db:
        kb = KnowledgeBaseStore.create(db, tenant_id=tenant_id, name=name,
                                        description=description, owner_id=user_id)
        logger.info("创建知识库: name=%s tenant=%s owner=%s", name, tenant_id, user_id,
                     extra={"request_id": rid})
        return {"id": str(kb.id), "name": kb.name, "tenant_id": kb.tenant_id,
                "owner_id": str(kb.owner_id) if kb.owner_id else None}


@app.get("/knowledge_bases/{kb_id}")
async def get_knowledge_base(kb_id: str, user: dict = Depends(get_current_user)):
    """获取知识库详情（需认证）"""
    rid = make_request_id()
    with get_session() as db:
        kb = KnowledgeBaseStore.get(db, kb_id)
        if not kb:
            logger.warning("知识库不存在: kb_id=%s", kb_id, extra={"request_id": rid})
            raise ErrorCode.KB_NOT_FOUND.exception()
        return {
            "id": str(kb.id),
            "name": kb.name,
            "tenant_id": kb.tenant_id,
            "owner_id": str(kb.owner_id) if kb.owner_id else None,
            "share_code": kb.share_code,
            "description": kb.description,
            "created_at": _local_iso(kb.created_at),
            "updated_at": _local_iso(kb.updated_at),
        }


# ===================================================================
#  知识库分享与成员管理
# ===================================================================

@app.post("/knowledge_bases/{kb_id}/share")
async def share_knowledge_base(kb_id: str, user: dict = Depends(get_current_user)):
    """生成或获取知识库的分享码（仅 owner 可操作）"""
    user_id = user["user_id"]
    with get_session() as db:
        kb = KnowledgeBaseStore.get(db, kb_id)
        if not kb:
            raise ErrorCode.KB_NOT_FOUND.exception()
        if str(kb.owner_id) != user_id:
            raise ErrorCode.FORBIDDEN.exception(detail="只有知识库创建者可以生成分享链接")

        if not kb.share_code:
            share_code = f"KB-{secrets.token_urlsafe(16)}"
            KnowledgeBaseStore.update_share_code(db, kb_id, share_code)
        else:
            share_code = kb.share_code

        return {"share_code": share_code, "kb_id": kb_id}


@app.post("/knowledge_bases/join/{share_code}")
async def join_knowledge_base(share_code: str, user: dict = Depends(get_current_user)):
    """通过分享码申请加入知识库"""
    user_id = user["user_id"]
    with get_session() as db:
        kb = KnowledgeBaseStore.get_by_share_code(db, share_code)
        if not kb:
            raise ErrorCode.KB_NOT_FOUND.exception(detail="分享码无效或知识库不存在")

        # 不能加入自己的知识库
        if str(kb.owner_id) == user_id:
            raise ErrorCode.CONFLICT.exception(detail="你是该知识库的创建者，无需加入")

        # 检查是否已申请过
        existing = KbMemberStore.get_by_user_and_kb(db, user_id, str(kb.id))
        if existing:
            if existing.status == KbMemberStatus.approved:
                return {"message": "你已是该知识库的成员", "kb_id": str(kb.id), "status": "approved"}
            elif existing.status == KbMemberStatus.pending:
                return {"message": "已提交加入申请，等待创建者批准", "kb_id": str(kb.id), "status": "pending"}
            else:
                raise ErrorCode.CONFLICT.exception(detail="你的加入申请已被拒绝")

        # 创建待批准的成员记录
        KbMemberStore.create(db, knowledge_base_id=str(kb.id), user_id=user_id)

        return {"message": "加入申请已提交，等待创建者批准", "kb_id": str(kb.id), "status": "pending"}


@app.post("/knowledge_bases/{kb_id}/members/{member_id}/approve")
async def approve_kb_member(kb_id: str, member_id: str, user: dict = Depends(get_current_user)):
    """批准成员加入知识库（仅 owner）"""
    user_id = user["user_id"]
    with get_session() as db:
        kb = KnowledgeBaseStore.get(db, kb_id)
        if not kb:
            raise ErrorCode.KB_NOT_FOUND.exception()
        if str(kb.owner_id) != user_id:
            raise ErrorCode.FORBIDDEN.exception(detail="只有知识库创建者可以审批成员")

        member = KbMemberStore.get(db, member_id)
        if not member or str(member.knowledge_base_id) != kb_id:
            raise ErrorCode.NOT_FOUND.exception(detail="成员申请不存在")

        if member.status != KbMemberStatus.pending:
            raise ErrorCode.CONFLICT.exception(detail=f"该申请已被{member.status.value}")

        KbMemberStore.update_status(db, member_id, KbMemberStatus.approved)
        return {"message": "已批准加入", "member_id": member_id, "status": "approved"}


@app.get("/knowledge_bases/{kb_id}/members")
async def list_kb_members(kb_id: str, user: dict = Depends(get_current_user)):
    """查看知识库成员列表（仅 owner）"""
    user_id = user["user_id"]
    with get_session() as db:
        kb = KnowledgeBaseStore.get(db, kb_id)
        if not kb:
            raise ErrorCode.KB_NOT_FOUND.exception()
        if str(kb.owner_id) != user_id:
            raise ErrorCode.FORBIDDEN.exception(detail="只有知识库创建者可以查看成员列表")

        members = KbMemberStore.list_by_kb(db, kb_id)
        result = []
        for m in members:
            result.append({
                "id": str(m.id),
                "user_id": str(m.user_id),
                "role": m.role.value,
                "status": m.status.value,
                "created_at": _local_iso(m.created_at),
            })
        return {"members": result, "kb_id": kb_id}


# ===================================================================
#  上传 & 处理
# ===================================================================

@app.post("/upload/{knowledge_base_id}")
async def upload_file(
    knowledge_base_id: str,
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    user: dict = Depends(get_current_user),
):
    """上传文件并启动后台处理流水线（需认证）。"""
    rid = make_request_id()
    tenant_id = user["tenant_id"]
    logger.info(
        "收到上传请求: name=%s kb=%s tenant=%s user=%s",
        file.filename, knowledge_base_id, tenant_id, user["user_id"],
        extra={"request_id": rid},
    )
    # 先保存文件到磁盘（不涉及DB，出错也没脏数据）
    content = await file.read()
    file_ext = Path(file.filename).suffix
    storage_path = f"uploads/{tenant_id}/{knowledge_base_id}/{uuid.uuid4()}{file_ext}"

    Path(storage_path).parent.mkdir(parents=True, exist_ok=True)
    with open(storage_path, "wb") as f:
        f.write(content)

    file_hash = hashlib.sha256(content).hexdigest()

    # DB 操作统一放在一个 session 中，异常时整体回滚
    with get_session() as db:
        # 验证知识库存在且属于该租户
        kb = KnowledgeBaseStore.get(db, knowledge_base_id)
        if not kb or kb.tenant_id != tenant_id:
            raise ErrorCode.KB_NOT_FOUND.exception()

        # 写 DB
        uploaded_file = UploadedFileStore.create(
            db=db,
            tenant_id=tenant_id,
            knowledge_base_id=knowledge_base_id,
            original_name=file.filename,
            storage_path=storage_path,
            content_type=file.content_type,
            size_bytes=len(content),
            file_hash=file_hash,
        )

        job = IngestionJobStore.create(
            db=db,
            tenant_id=tenant_id,
            knowledge_base_id=knowledge_base_id,
            file_id=str(uploaded_file.id),
        )

        job_id = str(job.id)
        file_id = str(uploaded_file.id)

        # 后台处理
        background_tasks.add_task(process_uploaded_document, job_id, file_id, rid)

        logger.info(
            "上传完成: job_id=%s file_id=%s size=%d",
            job_id, file_id, len(content),
            extra={"request_id": rid},
        )

        return {
            "job_id": job_id,
            "file_id": file_id,
            "file_name": file.filename,
            "status": "processing_started",
        }
    # ── 出 with 块 → commit；如果上面任意一步抛异常 → rollback，DB 无脏数据


async def process_uploaded_document(job_id: str, file_id: str, request_id: str = "-"):
    """后台处理流水线：解析 → 清洗 → 切片 → 向量索引。"""
    pid = make_request_id()
    log_extra = {"request_id": f"{request_id}/{pid}"}
    logger.info("后台任务开始: job_id=%s file_id=%s", job_id, file_id, extra=log_extra)
    try:
        with get_session() as db:
            uploaded_file = UploadedFileStore.get(db, file_id)
            if not uploaded_file:
                raise ErrorCode.FILE_NOT_FOUND.exception()

            # 查出知识库，后续都以知识库的 tenant_id 为准
            kb_id_str = str(uploaded_file.knowledge_base_id)
            kb = KnowledgeBaseStore.get(db, kb_id_str)
            if not kb:
                raise ErrorCode.KB_NOT_FOUND.exception()
            kb_tenant_id = kb.tenant_id

            IngestionJobStore.update_status(db, job_id, IngestionJobStatus.parsing)

            # 创建文档记录（tenant_id 以知识库为准）
            document = DocumentStore.create(
                db=db,
                tenant_id=kb_tenant_id,
                knowledge_base_id=kb_id_str,
                file_id=file_id,
                title=Path(uploaded_file.original_name).stem,
                source_uri=uploaded_file.storage_path,
            )

            # ← 在 session 内提取所有需要的字段，避免 detached 错误
            doc_id = str(document.id)
            storage_path = uploaded_file.storage_path
            tenant_id_str = kb_tenant_id
            original_name = uploaded_file.original_name

            IngestionJobStore.update_status(db, job_id, IngestionJobStatus.cleaning)

        # ---- 解析 & 切片（纯计算，不需 DB 连接） ----
        file_path = Path(storage_path)
        parser = _parser_registry.get_parser(file_path)
        parsed_doc = parser.parse(file_path)
        chunks: list[Chunk] = _chunker.chunk(parsed_doc)
        logger.info("解析完成: chunks=%d", len(chunks), extra=log_extra)

        # 组装成 DocumentChunkStore.bulk_create 需要的 dict 列表
        chunks_data = []
        for c in chunks:
            chunks_data.append({
                "tenant_id": tenant_id_str,
                "knowledge_base_id": kb_id_str,
                "document_id": doc_id,
                "file_id": file_id,
                "chunk_index": c.chunk_index,
                "content": c.content,
                "content_type": c.content_type,
                "heading_path": c.heading_path,
                "page_start": c.page_start,
                "page_end": c.page_end,
                "token_count": c.token_count,
                "keywords": c.keywords,
                "metadata": c.metadata,
                # 预生成 chunk_id 作为 Qdrant / ES 的文档 ID
                "chunk_id": c.chunk_id,
            })

        # ---- 入库 & 向量索引 ----
        with get_session() as db:
            IngestionJobStore.update_status(db, job_id, IngestionJobStatus.chunking)
            orm_chunks = DocumentChunkStore.bulk_create(db, chunks_data)

            IngestionJobStore.update_status(db, job_id, IngestionJobStatus.embedding)

            # ← 在 session 内提取 chunk 的纯数据，避免 detached 错误
            chunk_ids = [str(c.id) for c in orm_chunks]
            doc_id_from_orm = str(orm_chunks[0].document_id) if orm_chunks else ""

        # 从 orm_chunks + 纯字段重组为 QdrantChunkModel 需要的参数（session 已关，只需 content 等标量）
        # 将 chunks_data（dict 列表）与 chunk_ids 合并成 qdrant_models
        qdrant_models: list[QdrantChunkModel] = []
        for cd, cid in zip(chunks_data, chunk_ids):
            qdrant_models.append(
                QdrantChunkModel(
                    chunk_id=cid,
                    chunk_index=cd["chunk_index"],
                    document_id=cd["document_id"],
                    file_id=cd["file_id"],
                    file_name=original_name,
                    tenant_id=cd["tenant_id"],
                    knowledge_base_id=cd["knowledge_base_id"],
                    content_type=cd["content_type"],
                    content=cd["content"],
                    heading_path=cd["heading_path"],
                    page_start=cd["page_start"],
                    page_end=cd["page_end"],
                    keywords=cd["keywords"],
                    token_count=cd["token_count"],
                )
            )

        # 批量生成 embedding（在线程池中运行，避免阻塞事件循环）
        loop = asyncio.get_running_loop()
        vectors = await loop.run_in_executor(None, _batch_embed, [m.content for m in qdrant_models])

        # 批量写入 Qdrant
        qdrant_ok = True
        try:
            _qdrant.upsert_chunks(qdrant_models, vectors)
        except Exception:
            qdrant_ok = False

        # 批量写入 Elasticsearch
        es_ok = True
        try:
            _es.bulk_index_chunks(qdrant_models)
        except Exception:
            es_ok = False

        # 更新最终状态 & 同步状态
        with get_session() as db:
            DocumentStore.update_status(db, doc_id, DocumentStatus.active)
            IngestionJobStore.update_status(db, job_id, IngestionJobStatus.completed, progress=100)
            DocumentChunkStore.update_sync_status(
                db,
                document_id=doc_id,
                qdrant_sync=VectorSyncStatus.indexed if qdrant_ok else VectorSyncStatus.failed,
                es_sync=VectorSyncStatus.indexed if es_ok else VectorSyncStatus.failed,
            )

        # 清理临时文件
        try:
            tmp_path = Path(storage_path)
            if tmp_path.exists():
                tmp_path.unlink()
        except OSError:
            pass  # 删除失败不影响主流程

        logger.info("后台任务完成: job_id=%s chunks=%d qdrant=%s es=%s",
                     job_id, len(chunks), qdrant_ok, es_ok, extra=log_extra)

    except Exception as e:
        logger.error("后台任务失败: job_id=%s error=%s", job_id, str(e),
                      extra=log_extra, exc_info=True)
        with get_session() as db:
            IngestionJobStore.update_status(db, job_id, IngestionJobStatus.failed, error_message=str(e))


def _batch_embed(texts: list[str]) -> list[list[float]]:
    """批量调用 embedding API。"""
    import requests

    try:
        response = requests.post(
            f"{settings.EMBEDDING_BASE_URL}/embeddings",
            headers={
                "Authorization": f"Bearer {settings.EMBEDDING_API_KEY}",
                "Content-Type": "application/json",
            },
            json={"input": texts, "model": settings.EMBEDDING_MODEL},
            timeout=120,
        )
    except requests.exceptions.RequestException:
        raise ErrorCode.EMBEDDING_API_ERROR.exception(
            detail=f"无法连接到向量模型服务 ({settings.EMBEDDING_BASE_URL})，请检查服务是否已启动"
        ) from None

    if response.status_code != 200:
        raise ErrorCode.EMBEDDING_API_ERROR.exception(
            detail=f"向量模型服务返回异常 (HTTP {response.status_code})"
        )

    data = response.json()["data"]
    # data 可能无序，按 index 排序
    data.sort(key=lambda x: x["index"])
    return [item["embedding"] for item in data]


# ===================================================================
#  查询
# ===================================================================

@app.get("/jobs/{job_id}")
async def get_job_status(job_id: str, user: dict = Depends(get_current_user)):
    """查询导入任务状态（需认证）。"""
    with get_session() as db:
        job = IngestionJobStore.get(db, job_id)
        if not job:
            raise ErrorCode.JOB_NOT_FOUND.exception()
        return {
            "job_id": str(job.id),
            "status": job.status.value,
            "progress": job.progress,
            "error_message": job.error_message,
            "created_at": _local_iso(job.created_at),
            "updated_at": _local_iso(job.updated_at),
        }


@app.get("/documents/{doc_id}")
async def get_document(doc_id: str, user: dict = Depends(get_current_user)):
    """获取文档详情（需认证）。"""
    with get_session() as db:
        doc = DocumentStore.get(db, doc_id)
        if not doc:
            raise ErrorCode.DOC_NOT_FOUND.exception()
        return {
            "id": str(doc.id),
            "title": doc.title,
            "status": doc.status.value,
            "source_type": doc.source_type,
            "version": doc.version,
            "parser_name": doc.parser_name,
            "parser_version": doc.parser_version,
            "created_at": _local_iso(doc.created_at),
            "updated_at": _local_iso(doc.updated_at),
        }


@app.get("/search/{knowledge_base_id}")
async def search_documents(
    knowledge_base_id: str,
    query: str,
    limit: int = 10,
    user: dict = Depends(get_current_user),
):
    """在知识库中执行向量语义搜索（需认证）。"""
    rid = make_request_id()
    tenant_id = user["tenant_id"]
    logger.info("搜索请求: query=%s kb=%s tenant=%s user=%s",
                 query, knowledge_base_id, tenant_id, user["user_id"], extra={"request_id": rid})
    # 校验知识库存在且属于该租户
    with get_session() as db:
        kb = KnowledgeBaseStore.get(db, knowledge_base_id)
        if not kb:
            raise ErrorCode.KB_NOT_FOUND.exception()
        if kb.tenant_id != tenant_id:
            raise ErrorCode.TENANT_MISMATCH.exception()

    # 验证搜索词
    if not query or not query.strip():
        raise ErrorCode.INVALID_QUERY.exception()

    # 1. 生成查询向量
    loop = asyncio.get_running_loop()
    query_vector = await loop.run_in_executor(None, _single_embed, query)

    # 2. Qdrant 向量检索
    qdrant_hits = _qdrant.search(
        query_vector=query_vector,
        tenant_id=tenant_id,
        knowledge_base_ids=[knowledge_base_id],
        top_k=limit,
    )

    if not qdrant_hits:
        logger.info("搜索无结果: query=%s", query, extra={"request_id": rid})
        return {"results": [], "query": query, "knowledge_base_id": knowledge_base_id}

    # 3. 从 ES 补充完整内容
    chunk_ids = [h["chunk_id"] for h in qdrant_hits]
    full_contents = _es.get_full_contents(chunk_ids)

    results = []
    for hit in qdrant_hits:
        cid = hit["chunk_id"]
        results.append({
            "chunk_id": cid,
            "document_id": hit.get("document_id", ""),
            "file_id": hit.get("file_id", ""),
            "file_name": hit.get("file_name") or hit.get("file_name", ""),
            "content": full_contents.get(cid) or hit.get("content", ""),
            "score": hit["score"],
            "page_start": hit.get("page_start"),
            "page_end": hit.get("page_end"),
            "content_type": hit.get("content_type"),
            "heading_path": hit.get("heading_path"),
            "keywords": hit.get("keywords", []),
            "token_count": hit.get("token_count", 0),
        })

    logger.info("搜索完成: results=%d", len(results), extra={"request_id": rid})

    return {"results": results, "query": query, "knowledge_base_id": knowledge_base_id}


# ===================================================================
#  删除
# ===================================================================

@app.delete("/documents/{doc_id}")
async def delete_document(doc_id: str, user: dict = Depends(get_current_user)):
    """删除文档及其关联的所有数据（PG + Qdrant + ES）。需认证。"""
    with get_session() as db:
        doc = DocumentStore.get(db, doc_id)
        if not doc:
            raise ErrorCode.DOC_NOT_FOUND.exception()

        # 软删除
        DocumentStore.update_status(db, doc_id, DocumentStatus.deleted)

        # 删除分片记录
        deleted_count = DocumentChunkStore.delete_by_document(db, doc_id)

    # 从向量库删除
    try:
        _qdrant.delete_document_vectors(tenant_id=doc.tenant_id, document_id=doc_id)
    except Exception:
        pass  # Qdrant 删除失败不影响主流程

    try:
        _es.delete_document_chunks(document_id=doc_id)
    except Exception:
        pass

    return {
        "message": f"文档已删除，共删除 {deleted_count} 个分片",
        "deleted_chunks": deleted_count,
    }


class ChatRequest(BaseModel):
    """聊天请求"""
    message: str = Field(..., description="用户输入")
    session_id: str = Field("", description="会话 ID")
    context: str | None = Field(None, description="RAG 检索上下文")


# ===================================================================
#  聊天
# ===================================================================

@app.post("/chat")
async def chat(req: ChatRequest, user: dict = Depends(get_current_user)):
    """AI 聊天 — 调用 LLM 返回回复，自动保存聊天历史"""
    rid = make_request_id()

    try:
        # ---------- 构造 LLM 消息列表 ----------
        llm_messages = []

        # 1. RAG 系统提示词（如果有 context）
        if req.context:
            llm_messages.append(SystemMessage(
                content=f"""你是一个基于知识库回答的 AI 助手。

【核心规则】
1. 严格依据以下"参考内容"来回答问题。
2. 参考内容足够时给出详细准确的答案。
3. 参考内容不完整时，只回答相关内容，并说明"知识库中暂无更详细信息"。
4. 严禁编造参考内容中不存在的信息。
5. 回答要自然、简洁，不要提及"根据参考内容"之类的内部说明。

【参考内容】
{req.context}"""
            ))

        # 2. 加载聊天历史（如果有 session_id）
        if req.session_id:
            history = get_chat_history(req.session_id)
            for msg in history:
                if msg["role"] == "user":
                    llm_messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    llm_messages.append(AIMessage(content=msg["content"]))

        # 3. 当前用户消息
        llm_messages.append(HumanMessage(content=req.message))

        # ---------- 保存用户消息到历史 ----------
        if req.session_id:
            save_chat_message(req.session_id, "user", req.message)

        # ---------- 调用 LLM ----------
        response = chat_llm.invoke(llm_messages)
        content = response.content if hasattr(response, "content") else str(response)

        # ---------- 保存助手回复到历史 ----------
        if req.session_id:
            save_chat_message(req.session_id, "assistant", content)

        logger.info("AI 回复成功: len=%d history=%d request_id=%s",
                     len(content), len(llm_messages) - 1, rid)
        return {"response": content, "session_id": req.session_id}

    except Exception as e:
        logger.error("AI 调用失败: %s request_id=%s", str(e), rid)
        raise ErrorCode.INTERNAL_ERROR.exception(detail="AI 服务暂时不可用，请稍后重试")


class RenameRequest(BaseModel):
    """重命名请求"""
    title: str = Field(..., min_length=1, max_length=100, description="新标题")


@app.post("/chat/sessions")
async def create_session(user: dict = Depends(get_current_user)):
    """创建新会话"""
    import uuid
    session_id = str(uuid.uuid4())
    session = create_chat_session(session_id, user["user_id"])
    logger.info("会话已创建: session_id=%s", session_id)
    return session


@app.get("/chat/sessions")
async def list_sessions(user: dict = Depends(get_current_user)):
    """列出当前用户的所有会话"""
    sessions = list_chat_sessions(user["user_id"])
    return {"sessions": sessions}


@app.patch("/chat/sessions/{session_id}")
async def rename_session(session_id: str, req: RenameRequest, user: dict = Depends(get_current_user)):
    """重命名会话"""
    rename_chat_session(session_id, req.title)
    return {"message": "ok", "title": req.title}


@app.get("/chat/history/{session_id}")
async def chat_history(session_id: str, user: dict = Depends(get_current_user)):
    """获取指定会话的聊天历史"""
    history = get_chat_history(session_id)
    return {"messages": history, "session_id": session_id}


@app.delete("/chat/history/{session_id}")
async def delete_chat_history(session_id: str, user: dict = Depends(get_current_user)):
    """彻底删除指定会话（元数据 + 聊天记录）"""
    delete_chat_session(session_id, user["user_id"])
    logger.info("会话已删除: session_id=%s", session_id)
    return {"message": "会话已删除"}


# ===================================================================
#  Embedding 辅助
# ===================================================================

def _single_embed(text: str) -> list[float]:
    """单条文本 embedding。"""
    return _batch_embed([text])[0]


# ===================================================================
#  启动入口
# ===================================================================

if __name__ == "__main__":
    # 注册认证路由
    app.include_router(auth_router)

    # 注册 PPT Agent 路由（低耦合集成）
    from api.ppt_agent_router import router as ppt_agent_router
    app.include_router(ppt_agent_router)

    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
