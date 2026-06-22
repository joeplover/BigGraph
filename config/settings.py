"""全局配置 — 统一从环境变量读取，提供默认值"""
import os
from pathlib import Path

from dotenv import load_dotenv

# 加载 .env 文件（项目根目录）
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


class Settings:
    """所有外部服务的连接配置

    用法:
        from config.settings import settings
        settings.PG_HOST
        settings.QDRANT_URL
    """

    def __init__(self) -> None:
        # --- Runtime ---
        self.APP_ENV = os.getenv("APP_ENV", "development")
        self.JWT_SECRET_KEY = os.getenv(
            "JWT_SECRET_KEY",
            "biggraph-jwt-secret-key-change-in-production",
        )
        self.ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
        self.REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

        # --- PostgreSQL ---
        self.PG_HOST = os.getenv("PG_HOST", "127.0.0.1")
        self.PG_PORT = int(os.getenv("PG_PORT", "5432"))
        self.PG_USER = os.getenv("PG_USER", "workface")
        self.PG_PASSWORD = os.getenv("PG_PASSWORD", "678678")
        self.PG_DATABASE = os.getenv("PG_DATABASE", "workface")

        # --- Qdrant ---
        self.QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
        self.QDRANT_API_KEY = os.getenv("QDRANT_API_KEY") or None
        self.QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "enterprise_knowledge_chunks")
        self.QDRANT_VECTOR_SIZE = int(os.getenv("QDRANT_VECTOR_SIZE", "1024"))

        # --- Elasticsearch ---
        self.ES_HOSTS = os.getenv("ES_HOSTS", "http://localhost:9200").split(",")
        self.ES_USER = os.getenv("ES_USER", "elastic")
        self.ES_PASSWORD = os.getenv("ES_PASSWORD", "changeme")
        self.ES_INDEX = os.getenv("ES_INDEX", "enterprise_knowledge_chunks")
        self.ES_ANALYZER = os.getenv("ES_ANALYZER", "standard")

        # --- Embedding ---
        self.EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "bge-m3")
        self.EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL", "http://localhost:1233/v1")
        self.EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY", "123123")

        # --- Chunking ---
        self.CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "800"))
        self.CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "120"))

        # --- Timezone ---
        self.TIMEZONE = os.getenv("TIMEZONE", "Asia/Shanghai")

        # --- Logging ---
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
        self.LOG_DIR = os.getenv("LOG_DIR", "logs")

        # --- Redis ---
        self.REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
        self.REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
        self.REDIS_PASSWORD = os.getenv("REDIS_PASSWORD") or None
        self.REDIS_DB = int(os.getenv("REDIS_DB", "0"))

        # --- SMTP ---
        self.SMTP_HOST = os.getenv("SMTP_HOST", "smtp.qq.com")
        self.SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
        self.SMTP_USER = os.getenv("SMTP_USER", "")
        self.SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
        self.SMTP_USE_SSL = os.getenv("SMTP_USE_SSL", "true").lower() == "true"

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

    def validate_for_runtime(self) -> None:
        if self.APP_ENV.lower() != "production":
            return

        missing: list[str] = []
        if not os.getenv("JWT_SECRET_KEY"):
            missing.append("JWT_SECRET_KEY")
        if self.PG_PASSWORD in ("", "678678") and not os.getenv("DATABASE_URL"):
            missing.append("PG_PASSWORD or DATABASE_URL")
        if self.ES_PASSWORD in ("", "changeme"):
            missing.append("ES_PASSWORD")
        if self.EMBEDDING_API_KEY in ("", "123123"):
            missing.append("EMBEDDING_API_KEY")

        if missing:
            raise ValueError("Missing production configuration: " + ", ".join(missing))

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

    # --- Timezone ---
    TIMEZONE: str = os.getenv("TIMEZONE", "Asia/Shanghai")

    # --- Logging ---
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_DIR: str = os.getenv("LOG_DIR", "logs")

    # --- Redis ---
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_PASSWORD: str | None = os.getenv("REDIS_PASSWORD") or None
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))

    # --- SMTP ---
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.qq.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "465"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_USE_SSL: bool = os.getenv("SMTP_USE_SSL", "true").lower() == "true"


settings = Settings()
