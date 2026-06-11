from langchain_openai import OpenAIEmbeddings
from config.settings import settings


class EmbeddingService:
    def __init__(self) -> None:
        self.client = OpenAIEmbeddings(
            model=settings.EMBEDDING_MODEL, base_url=settings.EMBEDDING_BASE_URL,
            api_key=settings.EMBEDDING_API_KEY, check_embedding_ctx_length=False,
        )

    def embed_query(self, text: str) -> list[float]:
        if not text.strip():
            raise ValueError("不能对空文本做 embedding")
        return self.client.embed_query(text)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        cleaned = [t for t in texts if t and t.strip()]
        if not cleaned:
            return []
        vectors: list[list[float]] = []
        for start in range(0, len(cleaned), 32):
            vectors.extend(self.client.embed_documents(cleaned[start:start + 32]))
        return vectors
