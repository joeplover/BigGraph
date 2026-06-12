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
    pending = "pending"
    active = "active"
    archived = "archived"
    deleted = "deleted"
    failed = "failed"


class IngestionJobStatus(str, enum.Enum):
    """文档导入任务的各个阶段"""
    pending = "pending"
    parsing = "parsing"
    cleaning = "cleaning"
    chunking = "chunking"
    embedding = "embedding"
    indexing = "indexing"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class VectorSyncStatus(str, enum.Enum):
    """单一路径（Qdrant 或 ES）的同步状态"""
    pending = "pending"
    indexed = "indexed"
    partial = "partial"
    failed = "failed"


class KbMemberRole(str, enum.Enum):
    """知识库成员角色"""
    viewer = "viewer"
    editor = "editor"


class KbMemberStatus(str, enum.Enum):
    """知识库成员加入状态"""
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


# ========================================================================
# Mixin
# ========================================================================
class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.now, onupdate=datetime.now, nullable=False,
    )


class TenantMixin:
    tenant_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)


# ========================================================================
# PG 表模型
# ========================================================================
class User(Base, TimestampMixin):
    """系统用户"""
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True)
    is_verified: Mapped[bool] = mapped_column(default=False)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)


class KnowledgeBase(Base, TimestampMixin):
    __tablename__ = "knowledge_bases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    owner_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    share_code: Mapped[Optional[str]] = mapped_column(String(64), unique=True, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)


class KbMember(Base, TimestampMixin):
    """知识库成员"""
    __tablename__ = "kb_members"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    knowledge_base_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_bases.id"), index=True, nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True, nullable=False,
    )
    role: Mapped[KbMemberRole] = mapped_column(Enum(KbMemberRole), default=KbMemberRole.viewer)
    status: Mapped[KbMemberStatus] = mapped_column(Enum(KbMemberStatus), default=KbMemberStatus.pending)


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
