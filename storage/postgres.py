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
    KbMember,
    KbMemberRole,
    KbMemberStatus,
    KnowledgeBase,
    UploadedFile,
    User,
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
# User CRUD
# ========================================================================
class UserStore:
    @staticmethod
    def create(db: Session, username: str, password_hash: str, display_name: str | None = None,
               email: str | None = None) -> User:
        user = User(
            id=uuid.uuid4(),
            username=username,
            password_hash=password_hash,
            display_name=display_name or username,
            email=email,
            is_verified=bool(email),
            tenant_id=f"tenant_{uuid.uuid4().hex[:8]}",
            is_active=True,
        )
        db.add(user)
        db.flush()
        return user

    @staticmethod
    def get(db: Session, user_id: str) -> User | None:
        return db.get(User, user_id)

    @staticmethod
    def get_by_username(db: Session, username: str) -> User | None:
        return db.query(User).filter(User.username == username).first()

    @staticmethod
    def get_by_email(db: Session, email: str) -> User | None:
        return db.query(User).filter(User.email == email).first()

    @staticmethod
    def get_by_username_or_email(db: Session, account: str) -> User | None:
        """支持用户名或邮箱登录"""
        user = db.query(User).filter(User.username == account).first()
        if user:
            return user
        return db.query(User).filter(User.email == account).first()

    @staticmethod
    def update_verified(db: Session, user_id: str) -> None:
        user = db.get(User, user_id)
        if user:
            user.is_verified = True
            db.flush()


# ========================================================================
# KnowledgeBase CRUD
# ========================================================================
class KnowledgeBaseStore:
    @staticmethod
    def create(db: Session, tenant_id: str, name: str, description: str | None = None,
               owner_id: str | None = None) -> KnowledgeBase:
        kb = KnowledgeBase(id=uuid.uuid4(), tenant_id=tenant_id, name=name,
                           description=description, owner_id=owner_id)
        db.add(kb)
        db.flush()
        return kb

    @staticmethod
    def get(db: Session, kb_id: str) -> KnowledgeBase | None:
        return db.get(KnowledgeBase, kb_id)

    @staticmethod
    def list_by_tenant(db: Session, tenant_id: str) -> list[KnowledgeBase]:
        return db.query(KnowledgeBase).filter(KnowledgeBase.tenant_id == tenant_id).all()

    @staticmethod
    def list_by_owner(db: Session, owner_id: str) -> list[KnowledgeBase]:
        return db.query(KnowledgeBase).filter(KnowledgeBase.owner_id == owner_id).all()

    @staticmethod
    def update_share_code(db: Session, kb_id: str, share_code: str | None) -> KnowledgeBase | None:
        kb = db.get(KnowledgeBase, kb_id)
        if kb:
            kb.share_code = share_code
            db.flush()
        return kb

    @staticmethod
    def get_by_share_code(db: Session, share_code: str) -> KnowledgeBase | None:
        return db.query(KnowledgeBase).filter(KnowledgeBase.share_code == share_code).first()

    @staticmethod
    def delete(db: Session, kb_id: str) -> bool:
        """删除知识库记录"""
        kb = db.get(KnowledgeBase, kb_id)
        if not kb:
            return False
        db.delete(kb)
        db.flush()
        return True


# ========================================================================
# KbMember CRUD
# ========================================================================
class KbMemberStore:
    @staticmethod
    def create(db: Session, knowledge_base_id: str, user_id: str,
               role: KbMemberRole = KbMemberRole.viewer) -> KbMember:
        member = KbMember(
            id=uuid.uuid4(),
            knowledge_base_id=knowledge_base_id,
            user_id=user_id,
            role=role,
            status=KbMemberStatus.pending,
        )
        db.add(member)
        db.flush()
        return member

    @staticmethod
    def get(db: Session, member_id: str) -> KbMember | None:
        return db.get(KbMember, member_id)

    @staticmethod
    def get_by_user_and_kb(db: Session, user_id: str, kb_id: str) -> KbMember | None:
        return db.query(KbMember).filter(
            KbMember.user_id == user_id,
            KbMember.knowledge_base_id == kb_id,
        ).first()

    @staticmethod
    def list_by_kb(db: Session, kb_id: str) -> list[KbMember]:
        return db.query(KbMember).filter(KbMember.knowledge_base_id == kb_id).all()

    @staticmethod
    def list_approved_by_user(db: Session, user_id: str) -> list[KbMember]:
        return db.query(KbMember).filter(
            KbMember.user_id == user_id,
            KbMember.status == KbMemberStatus.approved,
        ).all()

    @staticmethod
    def update_status(db: Session, member_id: str, status: KbMemberStatus) -> KbMember | None:
        member = db.get(KbMember, member_id)
        if member:
            member.status = status
            db.flush()
        return member

    @staticmethod
    def delete_by_kb(db: Session, kb_id: str) -> int:
        """删除知识库的所有成员记录"""
        count = db.query(KbMember).filter(KbMember.knowledge_base_id == kb_id).delete(synchronize_session="fetch")
        db.flush()
        return count

    @staticmethod
    def user_can_access(db: Session, user_id: str, kb_id: str) -> bool:
        """检查用户是否有权限访问该知识库"""
        # 是 owner 吗？
        kb = db.get(KnowledgeBase, kb_id)
        if kb and str(kb.owner_id) == user_id:
            return True
        # 是已批准的成员吗？
        member = db.query(KbMember).filter(
            KbMember.user_id == user_id,
            KbMember.knowledge_base_id == kb_id,
            KbMember.status == KbMemberStatus.approved,
        ).first()
        return member is not None


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

    @staticmethod
    def delete_by_kb(db: Session, kb_id: str) -> int:
        """删除知识库的所有上传文件记录"""
        count = db.query(UploadedFile).filter(UploadedFile.knowledge_base_id == kb_id).delete(synchronize_session="fetch")
        db.flush()
        return count


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

    @staticmethod
    def delete_by_kb(db: Session, kb_id: str) -> int:
        """删除知识库的所有文档记录"""
        count = db.query(Document).filter(Document.knowledge_base_id == kb_id).delete(synchronize_session="fetch")
        db.flush()
        return count


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

    @staticmethod
    def delete_by_kb(db: Session, kb_id: str) -> int:
        """删除知识库的所有文档分片记录"""
        count = db.query(DocumentChunk).filter(DocumentChunk.knowledge_base_id == kb_id).delete(synchronize_session="fetch")
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

    @staticmethod
    def delete_by_kb(db: Session, kb_id: str) -> int:
        """删除知识库的所有导入任务记录"""
        count = db.query(IngestionJob).filter(IngestionJob.knowledge_base_id == kb_id).delete(synchronize_session="fetch")
        db.flush()
        return count
