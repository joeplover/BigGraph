from langchain_core.messages import HumanMessage
from langgraph.constants import END
from langgraph.graph import StateGraph
from langgraph.checkpoint.sqlite import SqliteSaver

from graphs.RAG_Chat_Graph.ChatNode import chat, search_node, permission_node, answer_node, router
from graphs.RAG_Chat_Graph.state import State, config

workflow = StateGraph(State)
workflow.add_node("chat", chat)
workflow.add_node("search_node", search_node)
workflow.add_node("permission_node", permission_node)
workflow.add_node("answer_node", answer_node)

# 入口：普通聊天 vs RAG 流程
workflow.set_conditional_entry_point(router, {"chat": "chat", "rag_chat": "search_node"})

# RAG 流程：检索 → 权限校验 → 回答
workflow.add_edge("search_node", "permission_node")
workflow.add_edge("permission_node", "answer_node")
workflow.add_edge("answer_node", END)

# 普通聊天到结束
workflow.add_edge("chat", END)

# 流程中可切换
workflow.add_conditional_edges("chat", router, {"chat": END, "rag_chat": "search_node"})


def _login_or_skip():
    """CLI 登录流程 — 可选登录，登录后获取 user_id 和 token"""
    import httpx

    print("=" * 50)
    print("  BigGraph RAG Chat CLI")
    print("=" * 50)
    print("  命令: /login <username> <password>  — 登录获取身份")
    print("        /register <user> <pass>       — 注册新用户")
    print("        /rag                         — 切换到 RAG 模式")
    print("        /chat                        — 切换回普通聊天")
    print("        /kb <知识库ID>                 — 设置知识库")
    print("        /me                          — 查看当前用户")
    print("        quit                         — 退出")
    print("=" * 50)

    user_info = {"user_id": "", "token": ""}

    while True:
        raw = input("\nuser:")
        if raw.startswith("/register"):
            parts = raw.split()
            if len(parts) < 3:
                print("AI: 用法: /register <用户名> <密码>")
                continue
            _, username, password = parts[:3]
            try:
                resp = httpx.post("http://localhost:8000/auth/register",
                                  json={"username": username, "password": password},
                                  timeout=10)
                if resp.status_code == 201 or resp.status_code == 200:
                    data = resp.json()
                    user_info["user_id"] = data["user"]["user_id"]
                    user_info["token"] = data["access_token"]
                    print(f"AI: 注册成功！欢迎 {data['user']['display_name']}")
                else:
                    print(f"AI: 注册失败: {resp.json().get('detail', '未知错误')}")
            except Exception as e:
                print(f"AI: 连接失败: {e}")
            continue

        if raw.startswith("/login"):
            parts = raw.split()
            if len(parts) < 3:
                print("AI: 用法: /login <用户名> <密码>")
                continue
            _, username, password = parts[:3]
            try:
                resp = httpx.post("http://localhost:8000/auth/login",
                                  json={"username": username, "password": password},
                                  timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    user_info["user_id"] = data["user"]["user_id"]
                    user_info["token"] = data["access_token"]
                    print(f"AI: 登录成功！欢迎 {data['user']['display_name']}")
                else:
                    print(f"AI: 登录失败: {resp.json().get('detail', '未知错误')}")
            except Exception as e:
                print(f"AI: 连接失败: {e}")
            continue

        if raw.startswith("/me"):
            if user_info["user_id"]:
                print(f"AI: 当前用户 ID: {user_info['user_id']}")
            else:
                print("AI: 未登录，请使用 /login 登录")
            continue

        break  # 不是命令，退出登录流程进入主循环

    return user_info, raw  # 返回用户信息和第一条消息


with SqliteSaver.from_conn_string("./dbcache/checkpoints.db") as memory:
    app = workflow.compile(checkpointer=memory)

    # 登录流程
    user_info, first_input = _login_or_skip()

    # 主聊天循环
    user_input = first_input
    while user_input not in ("quit", exit):
        # 命令处理
        if user_input.startswith("/"):
            cmd = user_input.split()
            if cmd[0] == "/rag":
                config["configurable"]["rag_mode"] = True
                print("AI: 已切换到 RAG 模式")
            elif cmd[0] == "/chat":
                config["configurable"]["rag_mode"] = False
                print("AI: 已切换到普通聊天模式")
            elif cmd[0] == "/kb" and len(cmd) > 1:
                config["configurable"]["kb_id"] = cmd[1]
                print(f"AI: 已设置知识库 ID = {cmd[1]}")
            elif cmd[0] == "/me":
                if user_info["user_id"]:
                    print(f"AI: 当前用户 ID: {user_info['user_id']}")
                else:
                    print("AI: 未登录")
            elif cmd[0] == "/login" or cmd[0] == "/register":
                print("AI: 请在启动时使用登录命令")
            else:
                print(f"AI: 未知命令。可用命令: /rag, /chat, /kb <知识库ID>, /me")
            user_input = input("user:")
            continue

        message = {
            "messages": [HumanMessage(content=user_input)],
            "rag_mode": config["configurable"].get("rag_mode", False),
            "kb_id": config["configurable"].get("kb_id", ""),
            "user_id": user_info["user_id"],
            "retrieved_chunks": [],
            "allowed_chunks": [],
            "permission_denied": False,
        }
        response = app.invoke(message, config)
        print("AI:", response["messages"][-1].content)
        user_input = input("user:")