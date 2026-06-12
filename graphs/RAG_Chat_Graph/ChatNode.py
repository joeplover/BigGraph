from graphs.RAG_Chat_Graph.Tools import search_documents
from graphs.RAG_Chat_Graph.LLM import llm
from graphs.RAG_Chat_Graph.state import State


def chat(state: State):
    """普通聊天"""
    return {"messages": [llm.invoke(state["messages"][-1].content)]}


def search_node(state: State):
    """RAG 检索节点 — 调用知识库 API 获取相关文档片段"""
    query = state["messages"][-1].content
    kb_id = state.get("kb_id", "")

    result = search_documents(kb_id=kb_id, query=query, limit=5)
    chunks = result.get("results", [])
    return {"retrieved_chunks": chunks}


def permission_node(state: State) -> dict:
    """权限校验节点 — 验证当前用户对知识库的访问权限"""
    user_id = state.get("user_id", "")
    kb_id = state.get("kb_id", "")
    chunks = state.get("retrieved_chunks", [])

    if not user_id:
        # CLI 模式或未登录 — 跳过权限校验
        return {"allowed_chunks": chunks}

    from storage.postgres import KbMemberStore, KnowledgeBaseStore, get_session

    with get_session() as db:
        kb = KnowledgeBaseStore.get(db, kb_id)
        if not kb:
            return {"allowed_chunks": [], "permission_denied": True}

        # 检查：是 owner 吗？
        if str(kb.owner_id) == user_id:
            return {"allowed_chunks": chunks}

        # 检查：是已批准的成员吗？
        has_access = KbMemberStore.user_can_access(db, user_id, kb_id)

    if not has_access:
        return {"allowed_chunks": [], "permission_denied": True}

    return {"allowed_chunks": chunks, "permission_denied": False}


def answer_node(state: State):
    """回答节点 — 组装 prompt 并调用 LLM"""
    query = state["messages"][-1].content
    kb_id = state.get("kb_id", "")
    chunks = state.get("allowed_chunks", [])
    denied = state.get("permission_denied", False)

    # 无权限
    if denied or (kb_id and not chunks and not state.get("retrieved_chunks")):
        prompt = f"""你是一个基于知识库回答的 AI 助手。

⚠️ 你当前使用的知识库 ({kb_id}) 无权访问或不存在，无法检索相关内容。
请告知用户联系知识库创建者申请权限。

用户问题：{query}"""
        return {"messages": [llm.invoke(prompt)]}

    # 无检索结果
    if not chunks:
        prompt = f"""你是一个严格基于知识库回答的 AI 助手。

⚠️ 当前处于 RAG 模式，但知识库中未找到与问题相关的任何内容。
请如实告知用户：知识库中暂无相关信息，不要编造答案。

用户问题：{query}"""
        return {"messages": [llm.invoke(prompt)]}

    # 正常组装上下文回答
    context = "\n\n".join(c["content"] for c in chunks)
    prompt = f"""你是一个严格基于知识库回答的 AI 助手。

【核心规则】
1. 严格依据以下"参考内容"回答问题。
2. 参考内容足够时给出详细准确答案。
3. 参考内容不完整时只回答相关内容，说明"知识库中暂无更详细信息"。
4. 严禁编造参考内容中不存在的信息。

【参考内容】
{context}

【用户问题】
{query}"""
    return {"messages": [llm.invoke(prompt)]}


def router(state: State) -> str:
    """根据 rag_mode 路由到对应节点"""
    if state.get("rag_mode"):
        return "rag_chat"
    return "chat"