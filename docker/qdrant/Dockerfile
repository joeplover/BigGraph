# =============================================================================
# Qdrant 自定义镜像 — 官方镜像 + curl（用于健康检查）
# =============================================================================
FROM qdrant/qdrant:v1.12.6

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*