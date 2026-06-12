from ppt_agent.state import State

from ppt_agent.web.materials import summarize_materials


def collect_m_node(state: State) -> dict:
    """收集用户资料。

    用户可能已经通过聊天上传了文件，也可能直接发送消息跳过。
    两种情况都直接继续流程。
    """
    material = state.get("material", _empty_material())
    requirement = state.get("requirement", {})

    raw_texts = material.get("raw_texts", [])

    # 如果用户上传了资料但没生成 summary，补上
    if raw_texts and not material.get("summary"):
        material_summary = summarize_materials(raw_texts)
        material["summary"] = material_summary
        material["topic"] = material_summary.get("topic", "")
        material["keywords"] = material_summary.get("keywords", [])
        material["key_points"] = material_summary.get("key_points", [])

    return {
        "material": material,
        "requirement": requirement,
        "status": "material_ready",
    }


def _empty_material() -> dict:
    return {
        "raw_texts": [],
        "file_paths": [],
        "summary": {},
        "topic": "",
        "keywords": [],
        "key_points": [],
    }
