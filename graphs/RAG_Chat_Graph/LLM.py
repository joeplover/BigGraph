import os

from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model = "deepseek-v4-flash",
    base_url = "https://api.deepseek.com/v1",
    api_key = os.getenv("DEEPSEEK_API_KEY")
)
