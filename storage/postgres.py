"""PostgreSQL 存储服务 — 连接管理 + CRUD 操作"""
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from config.settings import settings
from storage.models import (
    Base,
    Document,
    DocumentChunk,
    DocumentStatus,
    IngestionJob,
    IngestionJobStatus,
    KnowledgeBase,
    UploadedFile,
    VectorSyncStatus,
)

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    connect_args={"options": "-c timezone=Asia/Shanghai"},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def drop_db() -> None:
    Base.metadata.drop_all(bind=engine)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ========================================================================
# KnowledgeBase CRUD
# ========================================================================
class KnowledgeBaseStore:
    @staticmethod
    def create(db: Session, tenant_id: str, name: str, description: str | None = None) -> KnowledgeBase:
        kb = KnowledgeBase(id=uuid.uuid4(), tenant_id=tenant_id, name=name, description=description)
        db.add(kb)
        db.flush()
        return kb

    @staticmethod
    def get(db: Session, kb_id: str) -> KnowledgeBase | None:
        return db.get(KnowledgeBase, kb_id)

    @staticmethod
    def list_by_tenant(db: Session, tenant_id: str) -> list[KnowledgeBase]:
        return db.query(KnowledgeBase).filter(KnowledgeBase.tenant_id == tenant_id).all()


# ========================================================================
# UploadedFile CRUD
# ========================================================================
class UploadedFileStore:
    @staticmethod
    def create(db: Session, tenant_id: str, knowledge_base_id: str, original_name: str,
               storage_path: str, content_type: str | None = None, size_bytes: int = 0,
               file_hash: str | None = None) -> UploadedFile:
        record = UploadedFile(id=uuid.uuid4(), tenant_id=tenant_id, knowledge_base_id=knowledge_base_id,
                              original_name=original_name, storage_path=storage_path,
                              content_type=content_type, size_bytes=size_bytes, file_hash=file_hash)
        db.add(record)
        db.flush()
        return record

    @staticmethod
    def get(db: Session, file_id: str) -> UploadedFile | None:
        return db.get(UploadedFile, file_id)


# ========================================================================
# Document CRUD
# ========================================================================
class DocumentStore:
    @staticmethod
    def create(db: Session, tenant_id: str, knowledge_base_id: str, file_id: str, title: str,
               source_uri: str, parser_name: str | None = None, parser_version: str | None = None,
               metadata_: dict | None = None) -> Document:
        doc = Document(id=uuid.uuid4(), tenant_id=tenant_id, knowledge_base_id=knowledge_base_id,
                       file_id=file_id, title=title, source_type="upload", source_uri=source_uri,
                       status=DocumentStatus.pending, parser_name=parser_name,
                       parser_version=parser_version, metadata_=metadata_ or {})
        db.add(doc)
        db.flush()
        return doc

    @staticmethod
    def get(db: Session, doc_id: str) -> Document | None:
        return db.get(Document, doc_id)

    @staticmethod
    def update_status(db: Session, doc_id: str, status: DocumentStatus) -> Document | None:
        doc = db.get(Document, doc_id)
        if doc:
            doc.status = status
            db.flush()
        return doc


# ========================================================================
# DocumentChunk CRUD
# ========================================================================
class DocumentChunkStore:
    @staticmethod
    def bulk_create(db: Session, chunks: list[dict]) -> list[DocumentChunk]:
        rows = []
        for c in chunks:
            row = DocumentChunk(
                id=uuid.uuid4(), tenant_id=c["tenant_id"], knowledge_base_id=c["knowledge_base_id"],
                document_id=c["document_id"], file_id=c["file_id"], chunk_index=c["chunk_index"],
                content=c["content"], content_type=c.get("content_type", "text"),
                heading_path=c.get("heading_path"), page_start=c.get("page_start"),
                page_end=c.get("page_end"), token_count=c.get("token_count", 0),
                qdrant_point_id=c.get("chunk_id"), es_doc_id=c.get("chunk_id"),
                keywords=c.get("keywords", []), metadata_=c.get("metadata", {}),
                vector_status="pending",
            )
            rows.append(row)
        db.add_all(rows)
        db.flush()
        return rows

    @staticmethod
    def update_sync_status(db: Session, document_id: str, qdrant_sync: VectorSyncStatus | None = None,
                           es_sync: VectorSyncStatus | None = None) -> None:
        updates = {}
        if qdrant_sync is not None:
            updates["qdrant_sync"] = qdrant_sync
        if es_sync is not None:
            updates["es_sync"] = es_sync
        if qdrant_sync == VectorSyncStatus.indexed and es_sync == VectorSyncStatus.indexed:
            updates["vector_status"] = "indexed"
        if updates:
            db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).update(updates, synchronize_session="fetch")
            db.flush()

    @staticmethod
    def delete_by_document(db: Session, document_id: str) -> int:
        count = db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).delete(synchronize_session="fetch")
        db.flush()
        return count


# ========================================================================
# IngestionJob CRUD
# ========================================================================
class IngestionJobStore:
    @staticmethod
    def create(db: Session, tenant_id: str, knowledge_base_id: str, file_id: str) -> IngestionJob:
        job = IngestionJob(id=uuid.uuid4(), tenant_id=tenant_id, knowledge_base_id=knowledge_base_id,
                           file_id=file_id, status=IngestionJobStatus.pending, progress=0)
        db.add(job)
        db.flush()
        return job

    @staticmethod
    def get(db: Session, job_id: str) -> IngestionJob | None:
        return db.get(IngestionJob, job_id)

    @staticmethod
    def update_status(db: Session, job_id: str, status: IngestionJobStatus, progress: int | None = None,
                      error_message: str | None = None) -> IngestionJob | None:
        job = db.get(IngestionJob, job_id)
        if not job:
            return None
        job.status = status
        if progress is not None:
            job.progress = progress
        if error_message is not None:
            job.error_message = error_message
        db.flush()
        return job
