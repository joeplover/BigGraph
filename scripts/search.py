"""混合检索入口

用法:
    python scripts/search.py <query> --tenant T [--kb K1 K2 ...]
"""
import argparse
import sys
from pathlib import Path

_bg_root = Path(__file__).resolve().parent.parent
if str(_bg_root) not in sys.path:
    sys.path.insert(0, str(_bg_root))

from core.retrieval.hybrid import HybridRetrievalService


def search(query_text: str, tenant_id: str = "default",
           knowledge_base_ids: list[str] | None = None, top_k: int = 10) -> list[dict]:
    svc = HybridRetrievalService()
    return svc.search(query_text, tenant_id, knowledge_base_ids, top_k)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="混合检索")
    parser.add_argument("query", help="搜索文本")
    parser.add_argument("--tenant", default="default", help="租户 ID")
    parser.add_argument("--kb", nargs="*", help="知识库 ID 列表")
    parser.add_argument("--top-k", type=int, default=10, help="返回条数")
    args = parser.parse_args()

    results = search(args.query, args.tenant, args.kb, args.top_k)
    print(f"[检索] 找到 {len(results)} 条结果:\n")
    for r in results:
        print(f"  rrf={r['rrf_score']:.4f}  score={r.get('score', 0):.4f}  bm25={r.get('bm25_score', 0):.4f}")
        print(f"  {r.get('full_content', r['content'])[:120]}...\n")
