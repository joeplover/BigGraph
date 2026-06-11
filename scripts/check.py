"""三库数据一致性检查"""
import sys
from pathlib import Path

_bg_root = Path(__file__).resolve().parent.parent
if str(_bg_root) not in sys.path:
    sys.path.insert(0, str(_bg_root))

from storage.elasticsearch import ElasticsearchService
from storage.models import KnowledgeBase, UploadedFile, Document, DocumentChunk, IngestionJob
from storage.postgres import get_session
from storage.qdrant import QdrantService


def check():
    print("=" * 60)
    print("📦 PostgreSQL")
    print("=" * 60)
    with get_session() as db:
        for name, model in [("knowledge_bases", KnowledgeBase), ("uploaded_files", UploadedFile),
                            ("documents", Document), ("document_chunks", DocumentChunk),
                            ("ingestion_jobs", IngestionJob)]:
            count = db.query(model).count()
            print(f"  {name}: {count} 条")

    print("\n" + "=" * 60)
    print("🔍 Qdrant")
    print("=" * 60)
    try:
        svc = QdrantService()
        info = svc.client.get_collection(svc.collection)
        print(f"  points: {info.points_count}")
    except Exception as e:
        print(f"  ❌ {e}")

    print("\n" + "=" * 60)
    print("🔍 Elasticsearch")
    print("=" * 60)
    try:
        svc = ElasticsearchService()
        count = svc.client.count(index=svc.index)["count"]
        print(f"  docs: {count}")
    except Exception as e:
        print(f"  ❌ {e}")


if __name__ == "__main__":
    check()
