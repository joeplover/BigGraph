"""全局配置 — 统一从环境变量读取，提供默认值"""
import os


class Settings:
    """所有外部服务的连接配置

    用法:
        from config.settings import settings
        settings.PG_HOST
        settings.QDRANT_URL
    """

    # --- PostgreSQL ---
    PG_HOST: str = os.getenv("PG_HOST", "127.0.0.1")
    PG_PORT: int = int(os.getenv("PG_PORT", "5432"))
    PG_USER: str = os.getenv("PG_USER", "workface")
    PG_PASSWORD: str = os.getenv("PG_PASSWORD", "678678")
    PG_DATABASE: str = os.getenv("PG_DATABASE", "workface")

    @property
    def database_url(self) -> str:
        return os.getenv(
            "DATABASE_URL",
            f"postgresql+psycopg://{self.PG_USER}:{self.PG_PASSWORD}@{self.PG_HOST}:{self.PG_PORT}/{self.PG_DATABASE}",
        )

    # --- Qdrant ---
    QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    QDRANT_API_KEY: str | None = os.getenv("QDRANT_API_KEY") or None
    QDRANT_COLLECTION: str = os.getenv("QDRANT_COLLECTION", "enterprise_knowledge_chunks")
    QDRANT_VECTOR_SIZE: int = int(os.getenv("QDRANT_VECTOR_SIZE", "1024"))

    # --- Elasticsearch ---
    ES_HOSTS: list[str] = os.getenv("ES_HOSTS", "http://localhost:9200").split(",")
    ES_USER: str = os.getenv("ES_USER", "elastic")
    ES_PASSWORD: str = os.getenv("ES_PASSWORD", "changeme")
    ES_INDEX: str = os.getenv("ES_INDEX", "enterprise_knowledge_chunks")
    ES_ANALYZER: str = os.getenv("ES_ANALYZER", "standard")

    # --- Embedding ---
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "bge-m3")
    EMBEDDING_BASE_URL: str = os.getenv("EMBEDDING_BASE_URL", "http://localhost:1233/v1")
    EMBEDDING_API_KEY: str = os.getenv("EMBEDDING_API_KEY", "123123")

    # --- Chunking ---
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "800"))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "120"))


settings = Settings()
