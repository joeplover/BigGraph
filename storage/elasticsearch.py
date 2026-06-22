"""Elasticsearch 全文检索服务"""
from typing import Any

from elasticsearch import Elasticsearch

from config.settings import settings
from storage.models import QdrantChunkModel

# 索引 mapping（动态适配 ES_ANALYZER）
ES_INDEX_BODY = {
    "settings": {
        "analysis": {
            "analyzer": {"default": {"type": settings.ES_ANALYZER}},
        }
    },
    "mappings": {
        "dynamic": "strict",
        "properties": {
            "chunk_id": {"type": "keyword"},
            "chunk_index": {"type": "integer"},
            "document_id": {"type": "keyword"},
            "file_id": {"type": "keyword"},
            "file_name": {"type": "keyword"},
            "tenant_id": {"type": "keyword"},
            "knowledge_base_id": {"type": "keyword"},
            "content": {
                "type": "text",
                "analyzer": settings.ES_ANALYZER,
                "fields": {"keyword": {"type": "keyword", "ignore_above": 512}},
            },
            "content_type": {"type": "keyword"},
            "heading_path": {"type": "text", "fields": {"raw": {"type": "keyword"}}},
            "page_start": {"type": "integer"},
            "page_end": {"type": "integer"},
            "keywords": {"type": "keyword"},
            "token_count": {"type": "integer"},
            "metadata": {"type": "flattened"},
        },
    },
}


class ElasticsearchService:
    def __init__(self) -> None:
        self.client = Elasticsearch(settings.ES_HOSTS, basic_auth=(settings.ES_USER, settings.ES_PASSWORD))
        self.index = settings.ES_INDEX

    def ensure_index(self) -> None:
        if not self.client.indices.exists(index=self.index):
            self.client.indices.create(index=self.index, body=ES_INDEX_BODY)

    def delete_index(self) -> None:
        if self.client.indices.exists(index=self.index):
            self.client.indices.delete(index=self.index)

    def bulk_index_chunks(self, chunks: list[QdrantChunkModel]) -> Any:
        from elasticsearch.helpers import bulk

        def _generate():
            for c in chunks:
                yield {"_index": self.index, "_id": c.chunk_id, "_source": c.model_dump()}
        return bulk(self.client, _generate(), refresh="wait_for")

    def search_bm25(self, query: str, tenant_id: str, knowledge_base_ids: list[str] | None = None,
                    top_k: int = 30) -> list[dict]:
        filters = [{"term": {"tenant_id": tenant_id}}]
        if knowledge_base_ids:
            filters.append({"terms": {"knowledge_base_id": knowledge_base_ids}})
        resp = self.client.search(index=self.index, body={
            "query": {"bool": {"must": {"match": {"content": query}}, "filter": filters}},
            "size": top_k,
        })
        results = []
        for hit in resp["hits"]["hits"]:
            src = hit["_source"]
            results.append({
                "chunk_id": src.get("chunk_id", hit["_id"]),
                "document_id": src.get("document_id", ""),
                "file_name": src.get("file_name"),
                "content": src.get("content", ""),
                "heading_path": src.get("heading_path"),
                "page_start": src.get("page_start"),
                "page_end": src.get("page_end"),
                "content_type": src.get("content_type"),
                "score": float(hit["_score"]),
            })
        return results

    def get_full_contents(self, chunk_ids: list[str]) -> dict[str, str]:
        resp = self.client.search(index=self.index, body={
            "query": {"ids": {"values": chunk_ids}},
            "size": len(chunk_ids),
            "_source": ["chunk_id", "content"],
        })
        result: dict[str, str] = {}
        for hit in resp["hits"]["hits"]:
            src = hit["_source"]
            result[src.get("chunk_id", hit["_id"])] = src.get("content", "")
        return result

    def delete_document_chunks(self, document_id: str) -> Any:
        return self.client.delete_by_query(
            index=self.index, body={"query": {"term": {"document_id": document_id}}}, refresh=True,
        )

    def delete_knowledge_base_chunks(self, knowledge_base_id: str) -> Any:
        return self.client.delete_by_query(
            index=self.index,
            body={"query": {"term": {"knowledge_base_id": knowledge_base_id}}},
            refresh=True,
        )

    def delete_kb_chunks(self, knowledge_base_id: str) -> Any:
        return self.delete_knowledge_base_chunks(knowledge_base_id)

    def ping(self) -> bool:
        return self.client.ping()
