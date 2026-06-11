"""清理三库旧数据 → 重新验证

用法:
    python scripts/clean_run.py
"""
import sys
from pathlib import Path

_bg_root = Path(__file__).resolve().parent.parent
if str(_bg_root) not in sys.path:
    sys.path.insert(0, str(_bg_root))

from storage.elasticsearch import ElasticsearchService
from storage.models import KnowledgeBase, UploadedFile, Document, DocumentChunk, IngestionJob
from storage.postgres import get_session, init_db, drop_db
from storage.qdrant import QdrantService


def clean_all():
    """清理三库中所有旧数据"""
    print("=" * 60)
    print("清理旧数据...")
    print("=" * 60)

    # 1. Qdrant
    try:
        qdrant = QdrantService()
        qdrant.delete_collection()
        print("  Qdrant collection 已删除")
    except Exception as e:
        print(f"  Qdrant 清理: {e}")
    qdrant.ensure_collection()
    print("  Qdrant collection 已重建")

    # 2. ES
    try:
        es = ElasticsearchService()
        es.delete_index()
        print("  ES index 已删除")
    except Exception as e:
        print(f"  ES 清理: {e}")
    es.ensure_index()
    print("  ES index 已重建")

    # 3. PG — 重建所有表，确保 ORM 模型变更（如 default=datetime.now）生效
    drop_db()
    init_db()
    print("  PG 表已重建")

    print("\n清理完成，三库已恢复初始状态")


if __name__ == "__main__":
    clean_all()
