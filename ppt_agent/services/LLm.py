import os

from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model=os.getenv("DEEPSEEK_MODEL", "DeepSeek-V4-Flash[free]"),
    base_url=os.getenv("DEEPSEEK_BASE_URL", "https://cli.999554.xyz/v1"),
    api_key=os.getenv(
        "DEEPSEEK_API_KEY",
        "sk-uALuxh3EF7QYh8R8MUOfrQ6WuqWA4ksLoe1bzb8bsjhZIx79",
    ),
)
