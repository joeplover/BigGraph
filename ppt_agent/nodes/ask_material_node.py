from ppt_agent.state import State


def ask_m_node(state: State) -> dict:
    """需求完整后，提示用户可上传资料文件。"""
    return {
        "assistant_reply": (
            "需求信息已经完整。\n\n"
            "📎 你可以点击聊天框的附件按钮上传资料文件（支持 .txt, .md, .pdf, .docx, .xlsx, .pptx 等格式）\n\n"
            "直接发送消息跳过此步骤，继续生成方案。"
        ),
        "status": "waiting_material",
    }
