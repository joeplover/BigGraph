from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from ppt_agent.services.LLm import llm
from ppt_agent.state import State


def generate_s_l_node(state: State) -> dict:
    """根据 design_spec.md 生成 spec_lock.md。"""
    project_path = state.get("project_path")
    ppt_brief = state.get("ppt_brief", {})
    deck_outline = state.get("deck_outline", [])

    if not project_path:
        return {
            "status": "failed",
            "error": "缺少 project_path，无法生成 spec_lock.md。",
        }

    project_dir = Path(project_path)
    design_spec_path = project_dir / "design_spec.md"

    if not design_spec_path.exists():
        return {
            "status": "failed",
            "error": "缺少 design_spec.md，无法生成 spec_lock.md。",
        }

    print("Agent：正在生成 spec_lock.md...")

    try:
        design_spec = design_spec_path.read_text(encoding="utf-8")
    except Exception as exc:
        return {
            "status": "failed",
            "error": f"design_spec.md 读取失败：{exc}",
        }

    try:
        res = llm.invoke(
            [
                SystemMessage(
                    content="""
你是一个 PPT 执行规格生成助手。

你需要生成 spec_lock.md。

要求：
1. 只输出 Markdown。
2. 必须包含 canvas、colors、typography、icons、page_rhythm、forbidden。
3. colors 必须使用 HEX。
4. page_rhythm 必须覆盖每一页。
5. forbidden 必须包含 SVG 禁用项。
"""
                ),
                HumanMessage(
                    content=f"""
请根据下面的信息生成 spec_lock.md。

PPT Brief:
{ppt_brief}

页面大纲:
{deck_outline}

design_spec.md:
{design_spec}
"""
                ),
            ]
        )

        spec_lock_path = project_dir / "spec_lock.md"
        spec_lock_path.write_text(res.content, encoding="utf-8")
    except Exception as exc:
        return {
            "status": "failed",
            "error": f"spec_lock.md 生成失败：{exc}",
        }

    print(f"Agent：spec_lock.md 已生成：{spec_lock_path}")

    return {
        "status": "spec_lock_created",
        "assistant_reply": f"spec_lock.md 已生成：{spec_lock_path}",
    }
