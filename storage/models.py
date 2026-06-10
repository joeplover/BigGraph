"""数据模型 — PostgreSQL ORM 模型 + Qdrant payload 模型

对应子图: storage（存储子图）
"""
import enum
import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel
from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


# ========================================================================
# SQLAlchemy Base
# ========================================================================
class Base(DeclarativeBase):
    pass


# ========================================================================
# 枚举
# ========================================================================
class DocumentStatus(str, enum.Enum):
    """文档生命周期状态"""
    pending = "pending"   # 初始状态，文档刚创建但还没处理完
    active = "active"     # 文档已全部处理完成（含向量索引），可被检索
    archived = "archived" # 已归档，不再参与检索但保留数据
    deleted = "deleted"   # 软删除标记
    failed = "failed"     # 解析/处理流程中出错


class IngestionJobStatus(str, enum.Enum):
    """文档导入任务的各个阶段"""
    pending = "pending"     # 任务刚创建，等待处理
    parsing = "parsing"     # 正在解析文件（PDF/DOCX/TXT 等）
    cleaning = "cleaning"   # 正在文本清洗（去除零宽字符、合并断行等）
    chunking = "chunking"   # 正在将清洗后文本切片成 chunk
    embedding = "embedding" # 正在调用 embedding 模型生成向量
    indexing = "indexing"   # 正在写入 Qdrant + ES
    completed = "completed" # 全部处理完成，文档可被检索
    failed = "failed"       # 处理过程中出现不可恢复的错误
    cancelled = "cancelled" # 被用户手动取消


class VectorSyncStatus(str, enum.Enum):
    """单一路径（Qdrant 或 ES）的同步状态"""
    pending = "pending"   # 等待写入，还没开始处理
    indexed = "indexed"   # 写入成功，数据已可用
    partial = "partial"   # 写入部分成功（如批量写入时部分失败），需重试
    failed = "failed"     # 写入彻底失败（如连接异常），需人工介入


# ========================================================================
# Mixin
# ========================================================================
class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False,
    )


class TenantMixin:
    tenant_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)


# ========================================================================
# PG 表模型
# ========================================================================
class KnowledgeBase(Base, TimestampMixin):
    __tablename__ = "knowledge_bases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)


class UploadedFile(Base, TimestampMixin):
    __tablename__ = "uploaded_files"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    knowledge_base_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_bases.id"), nullable=False,
    )
    original_name: Mapped[str] = mapped_column(String(512), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    content_type: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    file_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)


class Document(Base, TenantMixin, TimestampMixin):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    knowledge_base_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_bases.id"), index=True, nullable=False,
    )
    file_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("uploaded_files.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), default="upload")
    source_uri: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    status: Mapped[DocumentStatus] = mapped_column(Enum(DocumentStatus), default=DocumentStatus.pending, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    parser_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    parser_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)


class DocumentChunk(Base, TenantMixin, TimestampMixin):
    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    knowledge_base_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_bases.id"), index=True, nullable=False,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), index=True, nullable=False,
    )
    file_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("uploaded_files.id"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(String(64), default="text")
    heading_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    page_start: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    page_end: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    qdrant_point_id: Mapped[Optional[str]] = mapped_column(String(128), index=True, nullable=True)
    es_doc_id: Mapped[Optional[str]] = mapped_column(String(128), index=True, nullable=True)
    qdrant_sync: Mapped[VectorSyncStatus] = mapped_column(Enum(VectorSyncStatus), default=VectorSyncStatus.pending)
    es_sync: Mapped[VectorSyncStatus] = mapped_column(Enum(VectorSyncStatus), default=VectorSyncStatus.pending)
    vector_status: Mapped[str] = mapped_column(String(64), default="pending")
    keywords: Mapped[list] = mapped_column(JSONB, default=list)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)


class IngestionJob(Base, TenantMixin, TimestampMixin):
    __tablename__ = "ingestion_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    knowledge_base_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_bases.id"), index=True, nullable=False,
    )
    file_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("uploaded_files.id"), nullable=False)
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True)
    status: Mapped[IngestionJobStatus] = mapped_column(Enum(IngestionJobStatus), default=IngestionJobStatus.pending)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)


# ========================================================================
# Qdrant payload 模型
# ========================================================================
class QdrantChunkModel(BaseModel):
    """Qdrant point 的 payload 结构

    注意：不包含 vector（vector 由 PointStruct.vector 承载）。
    content 字段仅存前 200 字符预览，完整内容存 ES。
    """
    chunk_id: str
    chunk_index: int
    document_id: str
    file_id: str
    file_name: str
    tenant_id: str
    knowledge_base_id: str
    content_type: str
    content: str
    heading_path: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    keywords: list[str] = []
    token_count: int = 0

    class Config:
        extra = "allow"
