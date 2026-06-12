import json
import re

from langchain_core.messages import HumanMessage, SystemMessage

from ppt_agent.services.LLm import llm

from ppt_agent.state import State


def collect_r_node(state: State) -> dict:
    """从用户消息中提取 PPT 需求信息。"""
    messages = state.get("messages", [])

    if not messages:
        return {
            "requirement": {},
            "status": "failed",
            "error": "没有找到用户消息。",
        }

    user_message = messages[-1].content.strip()

    if not user_message:
        return {
            "status": "collecting",
        }

    try:
        res = llm.invoke(
            [
                SystemMessage(
                    content="""
你是一个 PPT 需求信息提取工具。

CRITICAL：ONLY 提取用户明确提到的字段。绝对禁止自行推断或填充默认值。

正确示例：
用户说："我要做一个论文介绍PPT"
→ {"topic": "论文介绍", "use_case": "", "audience": "", "page_count": null, "style": "", "language": "zh-CN", "key_points": [], "source_files": []}

用户说："我要做一个20页的毕业答辩PPT，科技蓝风格，给老师看"
→ {"topic": "", "use_case": "毕业答辩", "audience": "老师", "page_count": 20, "style": "科技蓝", "language": "zh-CN", "key_points": [], "source_files": []}

用户说："帮我做一个项目汇报PPT"
→ {"topic": "项目汇报", "use_case": "", "audience": "", "page_count": null, "style": "", "language": "zh-CN", "key_points": [], "source_files": []}

规则：
1. 如果用户没有明确说出某个字段的值，该字段必须设为空字符串、null 或 []。
2. 禁止根据"论文"推测"学术风格"，禁止根据"答辩"推测"评审老师"。
3. 禁止自行设定 page_count，用户没说就是 null。
4. topic 是唯一可能从上下文推断的字段（如果用户说了"做一个XXX的PPT"），其他字段都不行。

只返回 JSON，不要返回任何解释文字。

JSON 格式如下：

{
  "topic": "PPT 题目",
  "use_case": "使用场景",
  "audience": "目标受众",
  "page_count": 20,
  "style": "视觉风格",
  "language": "zh-CN",
  "key_points": ["重点1", "重点2"],
  "source_files": []
}

如果某个字段没有提到：
- 字符串字段用空字符串 ""
- page_count 用 null
- key_points 用 []
- source_files 用 []
"""
                ),
                HumanMessage(content=user_message),
            ]
        )

        extracted_requirement = json.loads(_clean_json(res.content))
    except Exception as exc:
        return {
            "status": "failed",
            "error": f"需求信息解析失败：{exc}",
        }

    if not isinstance(extracted_requirement, dict):
        return {
            "status": "failed",
            "error": "需求信息解析失败：LLM 没有返回 JSON 对象。",
        }

    extracted_requirement = _normalize_requirement(extracted_requirement)

    old_requirement = state.get("requirement", {})
    requirement = {
        **old_requirement,
        **{
            key: value
            for key, value in extracted_requirement.items()
            if value not in ("", None, [])
        },
    }

    return {
        "requirement": requirement,
        "status": "collecting",
    }


def _normalize_requirement(requirement: dict) -> dict:
    page_count = requirement.get("page_count")

    if isinstance(page_count, str):
        match = re.search(r"\d+", page_count)
        requirement["page_count"] = int(match.group()) if match else None

    return requirement


def _clean_json(text: str) -> str:
    value = text.strip()

    if value.startswith("```"):
        value = re.sub(r"^```[a-zA-Z]*", "", value).strip()
        value = re.sub(r"```$", "", value).strip()

    return value
