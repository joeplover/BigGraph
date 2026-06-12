from ppt_agent.state import State


def confirm_p_node(state: State) -> dict:
    """把 PPT Brief 和页面大纲展示给用户确认。"""
    ppt_brief = state.get("ppt_brief", {})
    deck_outline = state.get("deck_outline", [])
    project_path = state.get("project_path", "")

    lines = [
        "项目资料已创建，请确认 PPT 制作方案：",
        "",
        "## 基本信息",
        f"- 主题：{ppt_brief.get('topic', '')}",
        f"- 使用场景：{ppt_brief.get('use_case', '')}",
        f"- 目标受众：{ppt_brief.get('audience', '')}",
        f"- 页数：{ppt_brief.get('page_count', '')}",
        f"- 风格：{ppt_brief.get('style', '')}",
        "",
        "## 页面大纲",
    ]

    for slide in deck_outline:
        lines.append(
            f"- P{slide.get('page')}: {slide.get('title')} - {slide.get('purpose')}"
        )

    lines.extend(
        [
            "",
            "如果方案没问题，请回复：确认",
            "如果需要调整，请直接告诉我要改哪里。",
        ]
    )

    return {
        "assistant_reply": "\n".join(lines),
        "status": "waiting_confirm",
    }