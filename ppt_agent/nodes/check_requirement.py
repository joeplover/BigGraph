from langchain_core.messages import HumanMessage, SystemMessage

from ppt_agent.state import State

def check_r_node(state:State):
    """
    检查需求是否足够创建 PPT Brief

    最小必填字段：
    topic
    use_case
    audience
    page_count
    style

    输出：
    state["requirement_complete"] = True 或 False
    state["missing_fields"] = ["audience", "page_count"]
    """

    required_fields = [
        "topic",
        "use_case",
        "audience",
        "page_count",
        "style",
    ]
    requirement = state.get("requirement",{})

    missing_fields = [
        field for field in required_fields if not requirement.get(field)
    ]

    return {
        "requirement_complete":len(missing_fields)==0,
        "missing_fields":missing_fields
    }

