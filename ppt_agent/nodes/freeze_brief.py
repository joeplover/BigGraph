from ppt_agent.state import State


def freeze_b_node(state:State):
    """把已完整的需求冻结成 PPT Brief。"""
    requirement = state.get("requirement",{})
    material = state.get("material", {})

    ppt_brief = {
        "topic": requirement.get("topic"),
        "use_case": requirement.get("use_case"),
        "audience": requirement.get("audience"),
        "page_count": requirement.get("page_count"),
        "style": requirement.get("style"),
        "language": requirement.get("language", "zh-CN"),
        "key_points": requirement.get("key_points", []),
        "source_files": requirement.get("source_files", []),
        "material": material,
    }
    return{
        "ppt_brief":ppt_brief,
        "status":"brief_ready"
    }
