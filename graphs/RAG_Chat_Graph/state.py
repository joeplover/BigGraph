from typing import Annotated, TypedDict

from langgraph.graph import add_messages


class State(TypedDict):
    messages:Annotated[list,add_messages]
    rag_mode: bool
    kb_id: str
    user_id: str
    retrieved_chunks: list
    allowed_chunks: list
    permission_denied: bool

config = {"configurable":{"thread_id":1}}