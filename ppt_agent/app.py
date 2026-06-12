from langchain_core.messages import HumanMessage

from ppt_agent.graph import app


INVISIBLE_CHARS = {
    "\u200b",
    "\u200c",
    "\u200d",
    "\ufeff",
}


def _clean_user_input(text: str) -> str:
    return "".join(
        char for char in text if char not in INVISIBLE_CHARS
    ).strip()


def main() -> None:
    state = {
        "messages": [],
        "requirement": {},
    }

    print("PPT Agent 已启动。输入 exit 退出。")

    while True:
        user_input = _clean_user_input(input("\n你："))

        if user_input.lower() in {"exit", "quit"}:
            break

        if not user_input:
            continue

        state.pop("assistant_reply", None)
        state["messages"].append(HumanMessage(content=user_input))

        if state.get("status") == "waiting_confirm":
            print("\nAgent：已收到回复，正在处理...")

        state = app.invoke(state)

        if state.get("assistant_reply"):
            print(f"\nAgent：{state['assistant_reply']}")

        if state.get("status") == "project_created":
            print(f"\nAgent：项目已创建：{state.get('project_path')}")
            break

        if state.get("status") == "ppt_exported":
            print(f"\nAgent：PPT 已生成：{state.get('pptx_path')}")
            break

        if state.get("status") == "failed":
            print(f"\nAgent：运行失败：{state.get('error')}")
            break


if __name__ == "__main__":
    main()
