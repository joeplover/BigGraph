from typing import Annotated, Literal, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class MaterialState(TypedDict, total=False):
    """用户补充资料的独立状态。"""

    raw_texts: list[str]
    file_paths: list[str]
    summary: dict
    topic: str
    keywords: list[str]
    key_points: list[str]


class State(TypedDict, total=False):
    """
    LangGraph 的共享状态。

    第一版目标：
    用户输入一句 PPT 需求，graph 逐步补全 requirement、brief、outline，
    最后调用 ppt-master 创建项目目录。
    """

    # 保存完整对话，不只保存用户消息。
    messages: Annotated[list[AnyMessage], add_messages]

    # 从用户聊天里提取出来的原始结构化需求。
    requirement: dict

    # 需求检查结果。
    requirement_complete: bool
    missing_fields: list[str]

    # 当前节点想回复给用户的话。
    assistant_reply: str

    # 当前流程状态。
    status: Literal[
        "collecting",
        "waiting_user",
        "brief_ready",
        "outline_ready",
        "project_created",
        "failed",
        "waiting_material",
        "material_ready",
        "waiting_confirm",
        "confirmed",
        "materials_written",
        "design_spec_created",
        "spec_lock_created",
        "svg_created",
        "ppt_exported",
    ]

    # 冻结后的 PPT 制作任务单。
    ppt_brief: dict

    # 用户补充资料。
    material: MaterialState

    # 页面大纲，一页一个 dict。
    deck_outline: list[dict]

    # ppt-master 创建出来的项目路径。
    project_path: str

    # 生成出来的 SVG 文件。
    svg_files: list[str]

    # 生成出来的 PPTX 文件。
    pptx_path: str

    # 出错时写入。
    error: str

    # 用户是否确认方案。
    confirmed: bool
