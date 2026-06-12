from ppt_agent.state import State


from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from ppt_agent.services.LLm import llm
from ppt_agent.state import State


def generate_d_s_node(state: State) -> dict:
    """根据 PPT Brief 和页面大纲生成 design_spec.md。"""
    project_path = state.get("project_path")
    ppt_brief = state.get("ppt_brief", {})
    deck_outline = state.get("deck_outline", [])

    if not project_path:
        return {
            "status": "failed",
            "error": "缺少 project_path，无法生成 design_spec.md。",
        }

    print("Agent：正在生成 design_spec.md...")

    try:
        res = llm.invoke(
            [
                SystemMessage(
                    content="""
你是一个 PPT 设计规格生成助手。

你需要根据用户需求和页面大纲，生成一份 design_spec.md。

要求：
1. 使用 Markdown。
2. 内容要清晰、可执行。
3. 包含项目信息、画布规格、视觉风格、配色、字体、页面大纲。
4. 不要生成 SVG。
5. 不要生成 PPTX。
6. 必须围绕用户提供的资料，不要生成通用模板内容。
"""
                ),
                HumanMessage(
                    content=f"""
请根据下面的信息生成 design_spec.md。

PPT Brief:

{ppt_brief}

页面大纲:

{deck_outline}
"""
                ),
            ]
        )

        design_spec = res.content

        design_spec_path = Path(project_path) / "design_spec.md"
        design_spec_path.write_text(design_spec, encoding="utf-8")
    except Exception as exc:
        return {
            "status": "failed",
            "error": f"design_spec.md 生成失败：{exc}",
        }

    print(f"Agent：design_spec.md 已生成：{design_spec_path}")

    return {
        "status": "design_spec_created",
        "assistant_reply": f"design_spec.md 已生成：{design_spec_path}",
    }
