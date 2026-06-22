from pathlib import Path


def test_delete_knowledge_base_route_exists_before_static_fallback() -> None:
    source = Path("api/ragControll.py").read_text(encoding="utf-8")

    delete_route = source.index('@app.delete("/knowledge_bases/{kb_id}")')
    static_fallback = source.index('@app.get("/{full_path:path}"')

    assert delete_route < static_fallback


def test_delete_knowledge_base_requires_owner_and_cleans_related_data() -> None:
    source = Path("api/ragControll.py").read_text(encoding="utf-8")

    start = source.index("async def delete_knowledge_base")
    end = source.index("\n\nclass ChatRequest", start)
    handler = source[start:end]

    helper = Path("services/kb_service.py").read_text(encoding="utf-8")

    assert "require_kb_owner(db, kb_id, user)" in handler
    assert 'str(kb.owner_id) != user["user_id"]' in helper
    assert "ErrorCode.FORBIDDEN.exception" in helper
    assert "DocumentChunkStore.delete_by_knowledge_base" in handler
    assert "IngestionJobStore.delete_by_knowledge_base" in handler
    assert "DocumentStore.delete_by_knowledge_base" in handler
    assert "UploadedFileStore.delete_by_knowledge_base" in handler
    assert "KbMemberStore.delete_by_knowledge_base" in handler
    assert "KnowledgeBaseStore.delete" in handler
