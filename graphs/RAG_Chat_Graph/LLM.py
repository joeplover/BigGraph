import os

from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model = "DeepSeek-V4-Flash[free]",
    base_url = "https://cli.999554.xyz/v1",
    api_key = "sk-uALuxh3EF7QYh8R8MUOfrQ6WuqWA4ksLoe1bzb8bsjhZIx79"
)
# llm = ChatOpenAI(
#     model = "deepseek-v4-flash",
#     base_url = "https://api.deepseek.com/v1",
#     api_key = os.getenv("DEEPSEEK_API_KEY")
# )
