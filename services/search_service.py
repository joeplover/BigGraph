from __future__ import annotations

from typing import Any

from storage.error_codes import ErrorCode


class SearchService:
    def __init__(self, hybrid: Any | None = None) -> None:
        self._hybrid = hybrid

    @property
    def hybrid(self) -> Any:
        if self._hybrid is None:
            from core.retrieval.hybrid import HybridRetrievalService

            self._hybrid = HybridRetrievalService()
        return self._hybrid

    def search(
        self,
        query: str,
        tenant_id: str,
        knowledge_base_id: str,
        limit: int = 10,
    ) -> list[dict]:
        if not query or not query.strip():
            raise ErrorCode.INVALID_QUERY.exception()

        rows = self.hybrid.search(
            query_text=query,
            tenant_id=tenant_id,
            knowledge_base_ids=[knowledge_base_id],
            top_k=limit,
        )
        return [self._normalize_result(row) for row in rows]

    @staticmethod
    def _normalize_result(row: dict) -> dict:
        return {
            "chunk_id": row.get("chunk_id", ""),
            "document_id": row.get("document_id", ""),
            "file_id": row.get("file_id", ""),
            "file_name": row.get("file_name", ""),
            "content": row.get("full_content") or row.get("content", ""),
            "score": row.get("score", 0.0) or 0.0,
            "rrf_score": row.get("rrf_score", 0.0) or 0.0,
            "bm25_score": row.get("bm25_score", 0.0) or 0.0,
            "page_start": row.get("page_start"),
            "page_end": row.get("page_end"),
            "content_type": row.get("content_type"),
            "heading_path": row.get("heading_path"),
            "keywords": row.get("keywords", []),
            "token_count": row.get("token_count", 0),
        }
