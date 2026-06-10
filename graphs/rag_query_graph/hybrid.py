from graphs.rag_query_graph.embedding import EmbeddingService
from graphs.rag_query_graph.rrf import reciprocal_rank_fusion
from storage.elasticsearch import ElasticsearchService
from storage.qdrant import QdrantService


class HybridRetrievalService:
    def __init__(self) -> None:
        self.qdrant = QdrantService()
        self.es = ElasticsearchService()
        self.embedder = EmbeddingService()

    def search(self, query_text: str, tenant_id: str, knowledge_base_ids: list[str] | None = None, top_k: int = 10) -> list[dict]:
        query_vector = self.embedder.embed_query(query_text)
        dense = self.qdrant.search(query_vector=query_vector, tenant_id=tenant_id, knowledge_base_ids=knowledge_base_ids, top_k=top_k * 3)
        for r in dense:
            r["_source"], r["bm25_score"] = "qdrant", 0.0
        bm25 = self.es.search_bm25(query=query_text, tenant_id=tenant_id, knowledge_base_ids=knowledge_base_ids, top_k=top_k * 3)
        for r in bm25:
            r["_source"], r["bm25_score"] = "es", r.get("score", 0.0)
        fused = reciprocal_rank_fusion(dense, bm25, k=60, top_k=top_k)
        chunk_ids = [r["chunk_id"] for r in fused if r.get("chunk_id")]
        full_contents = self.es.get_full_contents(chunk_ids)
        for r in fused:
            cid = r.get("chunk_id", "")
            if cid in full_contents:
                r["full_content"] = full_contents[cid]
        return fused
