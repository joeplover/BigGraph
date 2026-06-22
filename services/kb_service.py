from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from storage.error_codes import ErrorCode
from storage.models import KbMemberStatus, KnowledgeBase
from storage.postgres import KbMemberStore, KnowledgeBaseStore


def get_existing_knowledge_base(db: Session, kb_id: str) -> KnowledgeBase:
    kb = KnowledgeBaseStore.get(db, kb_id)
    if not kb:
        raise ErrorCode.KB_NOT_FOUND.exception()
    return kb


def require_kb_owner(db: Session, kb_id: str, user: dict) -> KnowledgeBase:
    kb = get_existing_knowledge_base(db, kb_id)
    if kb.tenant_id != user["tenant_id"]:
        raise ErrorCode.TENANT_MISMATCH.exception()
    if str(kb.owner_id) != user["user_id"]:
        raise ErrorCode.FORBIDDEN.exception(detail="Only the knowledge base owner can perform this operation")
    return kb


def require_kb_access(db: Session, kb_id: str, user: dict) -> KnowledgeBase:
    kb = get_existing_knowledge_base(db, kb_id)
    if kb.tenant_id != user["tenant_id"]:
        raise ErrorCode.TENANT_MISMATCH.exception()
    if str(kb.owner_id) == user["user_id"]:
        return kb

    member = KbMemberStore.get_by_user_and_kb(db, user["user_id"], kb_id)
    if member and member.status == KbMemberStatus.approved:
        return kb

    raise ErrorCode.FORBIDDEN.exception(detail="You do not have access to this knowledge base")


def require_kb_editor_or_owner(db: Session, kb_id: str, user: dict) -> KnowledgeBase:
    # Upload/edit is owner-only until editor semantics are implemented.
    return require_kb_owner(db, kb_id, user)
