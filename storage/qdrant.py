"""Qdrant 向量存储服务"""
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, FieldCondition, Filter, MatchAny, MatchValue, PointStruct, VectorParams,
)

from config.settings import settings
from storage.models import QdrantChunkModel


class QdrantService:
    def __init__(self, url: str | None = None, api_key: str | None = None) -> None:
        self.client = QdrantClient(url=url or settings.QDRANT_URL, api_key=api_key or settings.QDRANT_API_KEY)
        self.collection = settings.QDRANT_COLLECTION

    def ensure_collection(self) -> None:
        names = {c.name for c in self.client.get_collections().collections}
        if self.collection not in names:
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(size=settings.QDRANT_VECTOR_SIZE, distance=Distance.COSINE),
            )
        for field in ("tenant_id", "knowledge_base_id", "document_id", "file_id", "content_type"):
            try:
                self.client.create_payload_index(
                    collection_name=self.collection, field_name=field, field_schema="keyword",
                )
            except Exception:
                pass

    def upsert_chunks(self, chunks: list[QdrantChunkModel], vectors: list[list[float]]) -> Any:
        if len(chunks) != len(vectors):
            raise ValueError(f"chunks 数量 ({len(chunks)}) 与 vectors 数量 ({len(vectors)}) 不匹配")
        points = []
        for chunk, vector in zip(chunks, vectors, strict=True):
            payload = chunk.model_dump()
            if len(payload.get("content", "")) > 200:
                payload["content"] = payload["content"][:200]
            points.append(PointStruct(id=chunk.chunk_id, vector=vector, payload=payload))
        return self.client.upsert(collection_name=self.collection, points=points, wait=True)

    def search(self, query_vector: list[float], tenant_id: str,
               knowledge_base_ids: list[str] | None = None, top_k: int = 30,
               score_threshold: float | None = None) -> list[dict]:
        query_filter = Filter(must=[FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id))])
        if knowledge_base_ids:
            query_filter.must.append(
                FieldCondition(key="knowledge_base_id", match=MatchAny(any=knowledge_base_ids))
            )
        hits = self.client.search(
            collection_name=self.collection, query_vector=query_vector,
            query_filter=query_filter, limit=top_k, score_threshold=score_threshold, with_payload=True,
        )
        results = []
        for hit in hits:
            payload = hit.payload or {}
            results.append({
                "chunk_id": payload.get("chunk_id", ""),
                "document_id": payload.get("document_id", ""),
                "file_id": payload.get("file_id", ""),
                "file_name": payload.get("file_name"),
                "content": payload.get("content", ""),
                "heading_path": payload.get("heading_path"),
                "page_start": payload.get("page_start"),
                "page_end": payload.get("page_end"),
                "content_type": payload.get("content_type"),
                "keywords": payload.get("keywords", []),
                "token_count": payload.get("token_count", 0),
                "score": float(hit.score or 0),
            })
        return results

    def delete_document_vectors(self, tenant_id: str, document_id: str) -> None:
        self.client.delete(
            collection_name=self.collection,
            points_selector=Filter(must=[
                FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id)),
                FieldCondition(key="document_id", match=MatchValue(value=document_id)),
            ]),
        )

    def delete_collection(self) -> None:
        self.client.delete_collection(self.collection)
