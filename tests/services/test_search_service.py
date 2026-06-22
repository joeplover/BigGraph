from __future__ import annotations

import pytest
from fastapi import HTTPException

from services.search_service import SearchService


class _FakeHybrid:
    def __init__(self) -> None:
        self.calls = []

    def search(self, **kwargs):
        self.calls.append(kwargs)
        return [
            {
                "chunk_id": "chunk-1",
                "document_id": "doc-1",
                "file_id": "file-1",
                "file_name": "notes.txt",
                "content": "preview",
                "full_content": "full document content",
                "score": 0.8,
                "rrf_score": 0.07,
                "bm25_score": 1.5,
                "page_start": 2,
                "page_end": 3,
                "content_type": "text",
                "heading_path": "Intro",
                "keywords": ["rag"],
                "token_count": 42,
            }
        ]


def test_search_service_rejects_empty_query() -> None:
    service = SearchService(hybrid=_FakeHybrid())

    with pytest.raises(HTTPException) as exc_info:
        service.search(query="", tenant_id="tenant-a", knowledge_base_id="kb-1")

    assert exc_info.value.status_code == 400


def test_search_service_uses_hybrid_retrieval_and_normalizes_results() -> None:
    hybrid = _FakeHybrid()
    service = SearchService(hybrid=hybrid)

    results = service.search(
        query="hello",
        tenant_id="tenant-a",
        knowledge_base_id="kb-1",
        limit=5,
    )

    assert hybrid.calls == [
        {
            "query_text": "hello",
            "tenant_id": "tenant-a",
            "knowledge_base_ids": ["kb-1"],
            "top_k": 5,
        }
    ]
    assert results == [
        {
            "chunk_id": "chunk-1",
            "document_id": "doc-1",
            "file_id": "file-1",
            "file_name": "notes.txt",
            "content": "full document content",
            "score": 0.8,
            "rrf_score": 0.07,
            "bm25_score": 1.5,
            "page_start": 2,
            "page_end": 3,
            "content_type": "text",
            "heading_path": "Intro",
            "keywords": ["rag"],
            "token_count": 42,
        }
    ]
