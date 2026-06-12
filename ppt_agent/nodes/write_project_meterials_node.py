import json
from pathlib import Path

from ppt_agent.state import State


def w_p_m_node(state: State) -> dict:
    """把 agent 收集到的 brief 和 outline 写入 ppt-master 项目目录。"""
    project_path = state.get("project_path")
    ppt_brief = state.get("ppt_brief", {})
    deck_outline = state.get("deck_outline", [])

    if not project_path:
        return {
            "status": "failed",
            "error": "缺少 project_path，无法写入项目资料。",
        }

    project_dir = Path(project_path)
    sources_dir = project_dir / "sources"

    try:
        sources_dir.mkdir(parents=True, exist_ok=True)

        brief_path = project_dir / "agent_brief.json"
        outline_path = project_dir / "agent_outline.json"
        requirement_path = sources_dir / "user_requirement.md"

        brief_path.write_text(
            json.dumps(ppt_brief, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        outline_path.write_text(
            json.dumps(deck_outline, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        requirement_path.write_text(
            _build_requirement_markdown(ppt_brief, deck_outline),
            encoding="utf-8",
        )
    except Exception as exc:
        return {
            "status": "failed",
            "error": f"项目资料写入失败：{exc}",
        }

    return {
        "status": "materials_written",
        "assistant_reply": f"项目资料已写入：{project_path}",
    }


def _build_requirement_markdown(ppt_brief: dict, deck_outline: list[dict]) -> str:
    """把 brief 和 outline 转成给 ppt-master 后续使用的 Markdown 资料。"""
    lines = [
        "# PPT 制作需求",
        "",
        "## 基本信息",
        "",
        f"- 主题：{ppt_brief.get('topic', '')}",
        f"- 使用场景：{ppt_brief.get('use_case', '')}",
        f"- 目标受众：{ppt_brief.get('audience', '')}",
        f"- 页数：{ppt_brief.get('page_count', '')}",
        f"- 风格：{ppt_brief.get('style', '')}",
        f"- 语言：{ppt_brief.get('language', 'zh-CN')}",
        "",
        "## 内容重点",
        "",
    ]

    key_points = ppt_brief.get("key_points", [])
    material = ppt_brief.get("material", {})
    source_materials = material.get("raw_texts", [])
    material_summary = material.get("summary", {})

    if key_points:
        for point in key_points:
            lines.append(f"- {point}")
    else:
        lines.append("- 暂无")

    lines.extend(
        [
            "",
            "## 资料摘要",
            "",
            str(material_summary) if material_summary else "暂无",
            "",
            "## 用户补充资料",
            "",
        ]
    )

    if source_materials:
        for index, material in enumerate(source_materials, start=1):
            lines.append(f"### 资料 {index}")
            lines.append("")
            lines.append(material)
            lines.append("")
    else:
        lines.append("暂无")

    lines.extend(
        [
            "",
            "## 页面大纲",
            "",
        ]
    )

    for slide in deck_outline:
        page = slide.get("page", "")
        title = slide.get("title", "")
        purpose = slide.get("purpose", "")
        rhythm = slide.get("rhythm", "")

        lines.append(f"### P{page} {title}")
        lines.append("")
        lines.append(f"- 页面目的：{purpose}")
        lines.append(f"- 页面节奏：{rhythm}")
        lines.append("")

    return "\n".join(lines)
