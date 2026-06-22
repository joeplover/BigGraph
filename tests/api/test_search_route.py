from pathlib import Path


def test_search_route_delegates_to_search_service() -> None:
    source = Path("api/ragControll.py").read_text(encoding="utf-8")

    start = source.index("async def search_documents")
    end = source.index("\n\n# ===================================================================\n#  删除", start)
    handler = source[start:end]

    assert "_search_service.search(" in handler
    assert "_single_embed" not in handler
    assert "_qdrant.search" not in handler
    assert "_es.get_full_contents" not in handler
