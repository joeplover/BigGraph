import os

from langchain_openai import ChatOpenAI

from config.settings import settings

llm = ChatOpenAI(
    model=settings.LLM_MODEL,
    base_url=settings.LLM_BASE_URL,
    api_key=settings.LLM_API_KEY or os.getenv("DEEPSEEK_API_KEY", ""),
)