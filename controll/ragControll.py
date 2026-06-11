"""文档知识库管理系统 — FastAPI 控制器

负责:
  - 知识库 CRUD（创建 / 查询）
  - 文件上传 & 后台处理流水线
  - 向量索引（Qdrant）+ 全文索引（Elasticsearch）
  - 混合检索
  - 文档删除（PG + 向量库联动）
"""
from __future__ import annotations

import asyncio
import hashlib
import uuid
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile

from config.settings import settings
from graphs.document_ingestion_graph.chunker import StructureAwareChunker
from graphs.document_ingestion_graph.parser_base import Chunk
from graphs.document_ingestion_graph.registry import ParserRegistry
from storage.elasticsearch import ElasticsearchService
from storage.error_codes import ErrorCode
from storage.models import (
    DocumentChunk,
    DocumentStatus,
    IngestionJobStatus,
    QdrantChunkModel,
    VectorSyncStatus,
)
from storage.postgres import (
    DocumentChunkStore,
    DocumentStore,
    IngestionJobStore,
    KnowledgeBaseStore,
    UploadedFileStore,
    get_session,
)
from storage.qdrant import QdrantService

# ---------------------------------------------------------------------------
# FastAPI 应用
# ---------------------------------------------------------------------------

app = FastAPI(title="文档知识库管理系统", version="1.0.0")


# ---------------------------------------------------------------------------
# 全局异常处理器 — 统一错误响应格式
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """兜底处理器：将未捕获的异常转为标准错误响应"""
    from fastapi.responses import JSONResponse

    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.status_code * 1000,
                "message": exc.detail,
            },
        )
    # 非 HTTPException 的统一兜底
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

@app.post("/knowledge_bases/")
async def create_knowledge_base(tenant_id: str, name: str, description: str = ""):
    """创建知识库"""
    with get_session() as db:
        kb = KnowledgeBaseStore.create(db, tenant_id=tenant_id, name=name, description=description)
        return {"id": str(kb.id), "name": kb.name, "tenant_id": kb.tenant_id}


@app.get("/knowledge_bases/{kb_id}")
async def get_knowledge_base(kb_id: str):
    """获取知识库详情"""
    with get_session() as db:
        kb = KnowledgeBaseStore.get(db, kb_id)
        if not kb:
            raise ErrorCode.KB_NOT_FOUND.exception()
        return {
            "id": str(kb.id),
            "name": kb.name,
            "tenant_id": kb.tenant_id,
            "description": kb.description,
            "created_at": kb.created_at.isoformat(),
            "updated_at": kb.updated_at.isoformat(),
        }


# ===================================================================
#  上传 & 处理
# ===================================================================

@app.post("/upload/{knowledge_base_id}")
async def upload_file(
    knowledge_base_id: str,
    file: UploadFile = File(...),
    tenant_id: str = Form(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """上传文件并启动后台处理流水线。"""
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
        background_tasks.add_task(process_uploaded_document, job_id, file_id)

        return {
            "job_id": job_id,
            "file_id": file_id,
            "file_name": file.filename,
            "status": "processing_started",
        }
    # ── 出 with 块 → commit；如果上面任意一步抛异常 → rollback，DB 无脏数据


async def process_uploaded_document(job_id: str, file_id: str):
    """后台处理流水线：解析 → 清洗 → 切片 → 向量索引。"""
    try:
        with get_session() as db:
            uploaded_file = UploadedFileStore.get(db, file_id)
            if not uploaded_file:
                raise ErrorCode.FILE_NOT_FOUND.exception()

            IngestionJobStore.update_status(db, job_id, IngestionJobStatus.parsing)

            # 创建文档记录
            document = DocumentStore.create(
                db=db,
                tenant_id=uploaded_file.tenant_id,
                knowledge_base_id=str(uploaded_file.knowledge_base_id),
                file_id=file_id,
                title=Path(uploaded_file.original_name).stem,
                source_uri=uploaded_file.storage_path,
            )

            # ← 在 session 内提取所有需要的字段，避免 detached 错误
            doc_id = str(document.id)
            storage_path = uploaded_file.storage_path
            kb_id_str = str(uploaded_file.knowledge_base_id)
            tenant_id_str = uploaded_file.tenant_id
            original_name = uploaded_file.original_name

            IngestionJobStore.update_status(db, job_id, IngestionJobStatus.cleaning)

        # ---- 解析 & 切片（纯计算，不需 DB 连接） ----
        file_path = Path(storage_path)
        parser = _parser_registry.get_parser(file_path)
        parsed_doc = parser.parse(file_path)
        chunks: list[Chunk] = _chunker.chunk(parsed_doc)

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

    except Exception as e:
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
async def get_job_status(job_id: str):
    """查询导入任务状态。"""
    with get_session() as db:
        job = IngestionJobStore.get(db, job_id)
        if not job:
            raise ErrorCode.JOB_NOT_FOUND.exception()
        return {
            "job_id": str(job.id),
            "status": job.status.value,
            "progress": job.progress,
            "error_message": job.error_message,
            "created_at": job.created_at.isoformat(),
            "updated_at": job.updated_at.isoformat(),
        }


@app.get("/documents/{doc_id}")
async def get_document(doc_id: str):
    """获取文档详情。"""
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
            "created_at": doc.created_at.isoformat(),
            "updated_at": doc.updated_at.isoformat(),
        }


@app.get("/search/{knowledge_base_id}")
async def search_documents(
    knowledge_base_id: str,
    query: str,
    limit: int = 10,
    tenant_id: str = "default",
):
    """在知识库中执行向量语义搜索。"""
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

    return {"results": results, "query": query, "knowledge_base_id": knowledge_base_id}


# ===================================================================
#  删除
# ===================================================================

@app.delete("/documents/{doc_id}")
async def delete_document(doc_id: str):
    """删除文档及其关联的所有数据（PG + Qdrant + ES）。"""
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
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
