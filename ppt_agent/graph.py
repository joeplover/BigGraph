from langgraph.constants import END, START
from langgraph.graph import StateGraph

from ppt_agent.nodes.ask_followup import ask_f_node
from ppt_agent.nodes.ask_material_node import ask_m_node
from ppt_agent.nodes.check_requirement import check_r_node
from ppt_agent.nodes.check_user_confirm_node import check_u_c_node
from ppt_agent.nodes.collect_material_node import collect_m_node
from ppt_agent.nodes.collect_requirement import collect_r_node
from ppt_agent.nodes.confirm_plan_node import confirm_p_node
from ppt_agent.nodes.create_project import create_p_node
from ppt_agent.nodes.export_ppt_node import export_p_node
from ppt_agent.nodes.freeze_brief import freeze_b_node
from ppt_agent.nodes.generate_design_spec_node import generate_d_s_node
from ppt_agent.nodes.generate_spec_lock_node import generate_s_l_node
from ppt_agent.nodes.generate_svg_node import generate_s_v_g_node
from ppt_agent.nodes.plan_deck import plan_d_node
from ppt_agent.nodes.write_project_meterials_node import w_p_m_node
from ppt_agent.state import State


REQUIRED_FIELDS = ["topic", "use_case", "audience", "page_count", "style"]


def _looks_hallucinated(state: State) -> bool:
    """检查 requirement 是否可能是 LLM 脑补的，而非用户提供的。

    如果用户只发了一条短消息、没有走完追问流程、且所有字段都被填满，
    则很可能是 LLM 脑补了缺失字段的值。
    """
    requirement = state.get("requirement", {})
    filled_fields = [
        f for f in REQUIRED_FIELDS if requirement.get(f)
    ]

    # 只有部分字段有值 → 不像是脑补
    if len(filled_fields) < len(REQUIRED_FIELDS):
        return False

    # 检查用户消息数量 — 如果只有1条、且没有经历过追问
    messages = state.get("messages", [])
    user_msg_count = sum(
        1 for m in messages if hasattr(m, "type") and m.type == "human"
    )
    if user_msg_count > 1:
        return False

    # 检查最后一条用户消息长度 — 短消息不可能包含所有5个字段的详细内容
    last_user_msg = ""
    for m in reversed(messages):
        if hasattr(m, "type") and m.type == "human":
            last_user_msg = m.content
            break

    # 中文典型情况：一条短消息（<50字符）不可能同时给出主题、场景、受众、页数、风格
    if len(last_user_msg) < 50:
        return True

    return False


def route(state: State) -> str:
    if state.get("requirement_complete") == True:
        # 防御：所有字段齐全但用户只说了1句短消息 → LLM 脑补，需要追问
        if _looks_hallucinated(state):
            return "ask_followup_node"

        material = state.get("material", {})
        if material.get("raw_texts") or state.get("ppt_brief"):
            return "freeze_brief_node"
        return "ask_material_node"
    else:
        return "ask_followup_node"

def route_entry(state: State) -> str:
    if state.get("status") == "waiting_confirm":
        return "check_user_confirm_node"

    if state.get("status") == "waiting_material":
        return "collect_material_node"

    return "collect_requirement_node"

def route_confirm(state: State) -> str:
    if state.get("confirmed") == True:
        return "generate_design_spec_node"

    if state.get("status") == "waiting_confirm":
        return "end"

    return "collect_requirement_node"
wf = StateGraph(State)
wf.add_node("check_requirement_node",check_r_node)
wf.add_node("ask_followup_node",ask_f_node)
wf.add_node("ask_material_node",ask_m_node)
wf.add_node("collect_material_node",collect_m_node)
wf.add_node("collect_requirement_node",collect_r_node)
wf.add_node("create_project_node",create_p_node)
wf.add_node("freeze_brief_node",freeze_b_node)
wf.add_node("plan_deck_node",plan_d_node)
wf.add_node("write_project_materials_node",w_p_m_node)
wf.add_node("confirm_plan_node", confirm_p_node)
wf.add_node("check_user_confirm_node", check_u_c_node)
wf.add_node("generate_design_spec_node", generate_d_s_node)
wf.add_node("generate_spec_lock_node", generate_s_l_node)
wf.add_node("generate_svg_node", generate_s_v_g_node)
wf.add_node("export_ppt_node", export_p_node)

wf.add_conditional_edges(
    START,
    route_entry,
    {
        "collect_requirement_node": "collect_requirement_node",
        "check_user_confirm_node": "check_user_confirm_node",
        "collect_material_node": "collect_material_node",
    },
)

wf.add_edge("collect_requirement_node","check_requirement_node")

wf.add_conditional_edges(
    "check_user_confirm_node",
    route_confirm,
    {
        "generate_design_spec_node": "generate_design_spec_node",
        "collect_requirement_node": "collect_requirement_node",
        "end": END,
    },
)

wf.add_conditional_edges(
    "check_requirement_node",
    route
)
wf.add_edge("ask_followup_node",END)
wf.add_edge("ask_material_node",END)
wf.add_edge("collect_material_node","freeze_brief_node")
wf.add_edge("freeze_brief_node","plan_deck_node")
wf.add_edge("plan_deck_node","create_project_node")
wf.add_edge("create_project_node","write_project_materials_node")
wf.add_edge("write_project_materials_node","confirm_plan_node")
wf.add_edge("confirm_plan_node",END)
wf.add_edge("generate_design_spec_node","generate_spec_lock_node")
wf.add_edge("generate_spec_lock_node","generate_svg_node")
wf.add_edge("generate_svg_node","export_ppt_node")
wf.add_edge("export_ppt_node",END)

app = wf.compile()

