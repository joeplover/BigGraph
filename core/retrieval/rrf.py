def reciprocal_rank_fusion(qdrant_results: list[dict], es_results: list[dict], k: int = 60, top_k: int = 10) -> list[dict]:
    rrf: dict[str, float] = {}
    records: dict[str, dict] = {}
    for rank, item in enumerate(qdrant_results, start=1):
        cid = item.get("chunk_id", "")
        if cid:
            rrf[cid] = rrf.get(cid, 0.0) + 1.0 / (k + rank)
            records[cid] = item
    for rank, item in enumerate(es_results, start=1):
        cid = item.get("chunk_id", "")
        if cid:
            rrf[cid] = rrf.get(cid, 0.0) + 1.0 / (k + rank)
            if cid not in records:
                records[cid] = item
    sorted_ids = sorted(rrf, key=lambda cid: rrf[cid], reverse=True)[:top_k]
    results = []
    for cid in sorted_ids:
        item = dict(records[cid])
        item["rrf_score"] = rrf[cid]
        results.append(item)
    return results
