"""文档入库入口

用法:
    python scripts/ingest.py <文件路径> [--tenant T] [--kb K] [--name N]
"""
import argparse
import sys
from pathlib import Path

# 把项目根目录加入 sys.path
_bg_root = Path(__file__).resolve().parent.parent
if str(_bg_root) not in sys.path:
    sys.path.insert(0, str(_bg_root))

from graphs.document_ingestion_graph.chunker import StructureAwareChunker
from graphs.document_ingestion_graph.registry import ParserRegistry
from graphs.rag_query_graph.embedding import EmbeddingService
from storage.elasticsearch import ElasticsearchService
from storage.models import QdrantChunkModel, VectorSyncStatus
from storage.postgres import (
    DocumentChunkStore, DocumentStore, IngestionJobStore, KnowledgeBaseStore,
    UploadedFileStore, get_session, init_db, DocumentStatus, IngestionJobStatus,
)
from storage.qdrant import QdrantService


def add_document(
    file_path: str,
    tenant_id: str = "default",
    knowledge_base_id: str | None = None,
    file_name: str | None = None,
) -> dict:
    """解析 → 清洗 → 切片 → Embedding → 写入 PG + Qdrant + ES（事务一致）"""
    init_db()
    path = Path(file_path)
    fname = file_name or path.name
    parser = ParserRegistry().get_parser(path)

    qdrant_svc = QdrantService()
    es_svc = ElasticsearchService()
    qdrant_svc.ensure_collection()
    es_svc.ensure_index()

    chunker = StructureAwareChunker()
    embedder = EmbeddingService()

    pg_document_id: str | None = None
    qdrant_written = False
    es_written = False

    try:
        with get_session() as db:
            parsed = parser.parse(path)

            if knowledge_base_id:
                kb = KnowledgeBaseStore.get(db, knowledge_base_id)
                if not kb:
                    raise ValueError(f"知识库不存在: {knowledge_base_id}")
                kb_id = knowledge_base_id
            else:
                kb = KnowledgeBaseStore.create(db, tenant_id=tenant_id, name=parsed.title)
                kb_id = str(kb.id)

            uploaded = UploadedFileStore.create(
                db, tenant_id=tenant_id, knowledge_base_id=kb_id,
                original_name=fname, storage_path=str(path.resolve()),
                content_type=path.suffix.lower(), size_bytes=path.stat().st_size,
            )
            file_id = str(uploaded.id)

            job = IngestionJobStore.create(db, tenant_id=tenant_id, knowledge_base_id=kb_id, file_id=file_id)
            IngestionJobStore.update_status(db, str(job.id), IngestionJobStatus.parsing, 10)

            doc = DocumentStore.create(
                db, tenant_id=tenant_id, knowledge_base_id=kb_id, file_id=file_id,
                title=parsed.title, source_uri=str(path.resolve()),
                parser_name=parsed.metadata.get("parser"), parser_version="v1", metadata_=parsed.metadata,
            )
            pg_document_id = str(doc.id)
            job.document_id = doc.id
            IngestionJobStore.update_status(db, str(job.id), IngestionJobStatus.chunking, 45)

            chunks = chunker.chunk(parsed)
            if not chunks:
                raise ValueError("切片结果为空")

            chunk_dicts = [
                {k: getattr(c, k) for k in ("chunk_id", "chunk_index", "content", "content_type",
                 "heading_path", "page_start", "page_end", "token_count", "keywords", "metadata")}
                for c in chunks
            ]
            for d in chunk_dicts:
                d.update(tenant_id=tenant_id, knowledge_base_id=kb_id, document_id=pg_document_id, file_id=file_id)
            DocumentChunkStore.bulk_create(db, chunk_dicts)
            db.flush()

            IngestionJobStore.update_status(db, str(job.id), IngestionJobStatus.embedding, 65)
            vectors = embedder.embed_documents([c.content for c in chunks])
            if len(vectors) != len(chunks):
                raise ValueError(f"向量数量 ({len(vectors)}) 与 chunk 数量 ({len(chunks)}) 不匹配")

            IngestionJobStore.update_status(db, str(job.id), IngestionJobStatus.indexing, 80)

            qdrant_models = [
                QdrantChunkModel(
                    chunk_id=c.chunk_id, chunk_index=c.chunk_index, document_id=pg_document_id,
                    file_id=file_id, file_name=fname, tenant_id=tenant_id, knowledge_base_id=kb_id,
                    content_type=c.content_type, content=c.content, heading_path=c.heading_path,
                    page_start=c.page_start, page_end=c.page_end, keywords=c.keywords or [],
                    token_count=c.token_count,
                ) for c in chunks
            ]
            qdrant_svc.upsert_chunks(qdrant_models, vectors)
            qdrant_written = True

            es_models = [
                QdrantChunkModel(
                    chunk_id=c.chunk_id, chunk_index=c.chunk_index, document_id=pg_document_id,
                    file_id=file_id, file_name=fname, tenant_id=tenant_id, knowledge_base_id=kb_id,
                    content_type=c.content_type, content=c.content, heading_path=c.heading_path,
                    page_start=c.page_start, page_end=c.page_end, keywords=c.keywords or [],
                    token_count=c.token_count,
                ) for c in chunks
            ]
            es_svc.bulk_index_chunks(es_models)
            es_written = True

            DocumentChunkStore.update_sync_status(db, document_id=pg_document_id, qdrant_sync=VectorSyncStatus.indexed, es_sync=VectorSyncStatus.indexed)
            DocumentStore.update_status(db, pg_document_id, DocumentStatus.active)
            IngestionJobStore.update_status(db, str(job.id), IngestionJobStatus.completed, 100)

            return {"status": "ok", "document_id": pg_document_id, "knowledge_base_id": kb_id, "chunk_count": len(chunks)}

    except Exception as e:
        if qdrant_written and pg_document_id:
            try:
                qdrant_svc.delete_document_vectors(tenant_id=tenant_id, document_id=pg_document_id)
            except Exception as clean_err:
                print(f"[WARN] Qdrant 回滚失败: {clean_err}")
        if es_written and pg_document_id:
            try:
                es_svc.delete_document_chunks(document_id=pg_document_id)
            except Exception as clean_err:
                print(f"[WARN] ES 回滚失败: {clean_err}")
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="文档入库")
    parser.add_argument("file", help="文件路径")
    parser.add_argument("--tenant", default="default", help="租户 ID")
    parser.add_argument("--kb", help="知识库 ID（不传自动创建）")
    parser.add_argument("--name", help="文件展示名")
    args = parser.parse_args()

    if not Path(args.file).exists():
        print(f"[错误] 文件不存在: {args.file}")
        sys.exit(1)

    result = add_document(args.file, args.tenant, args.kb, args.name)
    print(f"[结果] {result}")
