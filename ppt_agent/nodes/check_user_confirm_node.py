from ppt_agent.state import State


CONFIRM_WORDS = {
    "确认",
    "同意",
    "可以",
    "没问题",
    "开始",
    "继续",
    "ok",
    "yes",
    "y",
}

NEGATIVE_WORDS = {
    "不确认",
    "先不确认",
    "不同意",
    "不可以",
    "有问题",
}

INVISIBLE_CHARS = {
    "\u200b",
    "\u200c",
    "\u200d",
    "\ufeff",
}


def check_u_c_node(state: State) -> dict:
    """检查用户是否确认 PPT 制作方案。"""
    messages = state.get("messages", [])

    if not messages:
        return {
            "confirmed": False,
            "status": "waiting_confirm",
            "assistant_reply": "请回复“确认”后继续。",
        }

    user_text = _clean_text(messages[-1].content).lower()
    clean_text = user_text.strip(" ，,。.;；!！?？")

    if not clean_text:
        return {
            "confirmed": False,
            "status": "waiting_confirm",
            "assistant_reply": "如果方案没问题，请回复“确认”。如果要修改，请直接告诉我要改哪里。",
        }

    confirmed = clean_text in CONFIRM_WORDS or (
        "确认" in clean_text and not any(word in clean_text for word in NEGATIVE_WORDS)
    )

    if confirmed:
        return {
            "confirmed": True,
            "status": "confirmed",
        }

    if clean_text in NEGATIVE_WORDS:
        return {
            "confirmed": False,
            "status": "waiting_confirm",
            "assistant_reply": "请直接告诉我要改哪里，例如：把页数改成 10 页，风格改成科技风。",
        }

    return {
        "confirmed": False,
        "status": "collecting",
    }


def _clean_text(text: str) -> str:
    return "".join(
        char for char in text if char not in INVISIBLE_CHARS
    ).strip()
