from langchain_core.messages import SystemMessage

from ppt_agent.state import State

FIELD_QUESTIONS = {
    "topic": "PPT 的具体题目是什么？",
    "use_case": "这份 PPT 用在什么场景？比如毕业答辩、项目汇报、商业路演。",
    "audience": "这份 PPT 是给谁看的？比如答辩老师、领导、客户。",
    "page_count": "你希望大概做多少页？",
    "style": "你希望 PPT 是什么风格？比如科技蓝、商务简洁、学术答辩风。",
}
def ask_f_node(state:State):
    """需求不完整时，向用户追问。"""
    missing_fields = state.get("missing_fields", [])
    questions = [
        FIELD_QUESTIONS[field] for field in missing_fields if field in FIELD_QUESTIONS
    ]
    assistant_reply = "我还需要确认这些信息：\n"+"\n".join(
        f"{index}.{question}"
        for index,question in enumerate(questions,start=1)
    )
    return {
        "assistant_reply": assistant_reply,
        "status": "waiting_user",
    }