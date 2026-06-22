import os

from langchain_openai import ChatOpenAI

from config.settings import settings

llm = ChatOpenAI(
      model = "DeepSeek-V4-Flash[free]",
      base_url = "https://cli.999554.xyz/v1",
      api_key = "sk-uALuxh3EF7QYh8R8MUOfrQ6WuqWA4ksLoe1bzb8bsjhZIx79"
)
