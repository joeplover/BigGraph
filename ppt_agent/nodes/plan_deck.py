import json
import re

from langchain_core.messages import HumanMessage, SystemMessage

from ppt_agent.services.LLm import llm
from ppt_agent.state import State


def plan_d_node(state: State) -> dict:
    """根据 PPT Brief 生成页面大纲。"""
    ppt_brief = state.get("ppt_brief", {})
    material = ppt_brief.get("material", {})
    source_materials = material.get("raw_texts", [])
    material_summary = material.get("summary", {})
    page_count = int(ppt_brief.get("page_count") or 0)

    try:
        res = llm.invoke(
            [
                SystemMessage(
                    content=(
                        "你是一个 PPT 大纲规划助手。"
                        "必须优先依据用户提供的资料生成大纲。"
                        "禁止生成通用答辩模板。"
                        "请只返回 JSON 数组，不要返回解释文字。"
                    )
                ),
                HumanMessage(
                    content=f"""
请根据下面的 PPT Brief 生成 PPT 页面大纲：

{ppt_brief}

资料摘要：
{material_summary}

用户补充资料：
{_limit_materials(source_materials)}

强制要求：
1. 页面标题必须围绕资料主题：{material_summary.get("topic", ppt_brief.get("topic", ""))}。
2. 如果资料是论文，必须体现资料中的研究对象、研究方法、核心结果、结论展望。
3. 不要写“研究背景、研究方法、研究结果”这种空泛标题，必须结合资料具体内容。
4. 不要编造用户资料之外的内容。
5. 必须生成 {page_count} 页，不能多也不能少。
6. page 字段必须从 1 连续编号到 {page_count}。
7. 必须围绕资料关键词生成：{material_summary.get("keywords", [])}。
8. 禁止出现用户资料中没有的研究对象、研究方法、实验结论或专有名词。

输出格式必须是 JSON 数组，例如：

[
  {{
    "page": 1,
    "title": "封面",
    "purpose": "展示题目、学生、导师",
    "rhythm": "anchor"
  }},
  {{
    "page": 2,
    "title": "目录",
    "purpose": "展示汇报结构",
    "rhythm": "breathing"
  }}
]

rhythm 只能从这三个里面选：
- anchor
- breathing
- dense
"""
                ),
            ]
        )

        deck_outline = json.loads(_clean_json(res.content))
    except Exception as exc:
        return {
            "status": "failed",
            "error": f"PPT 大纲生成失败：{exc}",
        }

    deck_outline = _normalize_deck_outline(deck_outline, page_count)

    if page_count and len(deck_outline) != page_count:
        try:
            retry_res = llm.invoke(
                [
                    SystemMessage(
                        content=(
                            "你是一个 PPT 大纲修正工具。"
                            "请只返回 JSON 数组，不要返回解释文字。"
                        )
                    ),
                    HumanMessage(
                        content=f"""
当前大纲页数是 {len(deck_outline)}，但用户要求 {page_count} 页。

请根据原始 PPT Brief 和用户资料，重新生成严格 {page_count} 页的大纲。

PPT Brief:
{ppt_brief}

资料摘要：
{material_summary}

用户补充资料：
{_limit_materials(source_materials)}

当前错误大纲：
{deck_outline}

要求：
1. 必须返回 JSON 数组。
2. 必须正好 {page_count} 个对象。
3. page 必须从 1 到 {page_count} 连续编号。
4. 页面标题必须结合资料具体内容。
"""
                    ),
                ]
            )

            deck_outline = json.loads(_clean_json(retry_res.content))
            deck_outline = _normalize_deck_outline(deck_outline, page_count)
        except Exception:
            deck_outline = []

    if page_count and len(deck_outline) != page_count:
        deck_outline = _build_fallback_outline(ppt_brief, material_summary, page_count)

    return {
        "deck_outline": deck_outline,
        "status": "outline_ready",
    }


def _limit_materials(source_materials: list[str]) -> str:
    text = "\n\n".join(source_materials)
    return text[:12000]


def _normalize_deck_outline(deck_outline: list, page_count: int) -> list[dict]:
    if not isinstance(deck_outline, list):
        return []

    normalized = []

    for index, slide in enumerate(deck_outline, start=1):
        if not isinstance(slide, dict):
            continue

        normalized.append(
            {
                "page": index,
                "title": slide.get("title", f"第 {index} 页"),
                "purpose": slide.get("purpose", ""),
                "rhythm": slide.get("rhythm", "breathing"),
            }
        )

    if page_count and len(normalized) > page_count:
        normalized = normalized[:page_count]

    return normalized


def _build_fallback_outline(
    ppt_brief: dict,
    material_summary: dict,
    page_count: int,
) -> list[dict]:
    topic = material_summary.get("topic") or ppt_brief.get("topic") or "PPT"
    key_points = material_summary.get("key_points") or material_summary.get("keywords") or []

    slides = [
        {
            "page": 1,
            "title": "封面",
            "purpose": f"展示 {topic} 的题目和汇报信息",
            "rhythm": "anchor",
        }
    ]

    if page_count >= 2:
        slides.append(
            {
                "page": 2,
                "title": "目录",
                "purpose": "展示本次汇报的主要结构",
                "rhythm": "breathing",
            }
        )

    middle_count = max(page_count - len(slides) - 1, 0)

    for index in range(middle_count):
        point = key_points[index] if index < len(key_points) else topic
        page = len(slides) + 1
        slides.append(
            {
                "page": page,
                "title": str(point)[:24],
                "purpose": f"围绕 {point} 展开说明",
                "rhythm": "dense",
            }
        )

    if len(slides) < page_count:
        slides.append(
            {
                "page": page_count,
                "title": "总结与展望",
                "purpose": f"总结 {topic} 的核心内容并说明后续方向",
                "rhythm": "breathing",
            }
        )

    return slides[:page_count]


def _clean_json(text: str) -> str:
    value = text.strip()

    if value.startswith("```"):
        value = re.sub(r"^```[a-zA-Z]*", "", value).strip()
        value = re.sub(r"```$", "", value).strip()

    return value
