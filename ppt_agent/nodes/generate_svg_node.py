import re
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from ppt_agent.services.LLm import llm
from ppt_agent.state import State


def generate_s_v_g_node(state: State) -> dict:
    """根据 spec_lock.md 和页面大纲逐页生成 SVG。"""
    project_path = state.get("project_path")
    deck_outline = state.get("deck_outline", [])
    ppt_brief = state.get("ppt_brief", {})

    if not project_path:
        return {
            "status": "failed",
            "error": "缺少 project_path，无法生成 SVG。",
        }

    project_dir = Path(project_path)
    spec_lock_path = project_dir / "spec_lock.md"

    if not spec_lock_path.exists():
        return {
            "status": "failed",
            "error": "缺少 spec_lock.md，无法生成 SVG。",
        }

    svg_output_dir = project_dir / "svg_output"
    svg_output_dir.mkdir(parents=True, exist_ok=True)

    generated_files = []
    total = len(deck_outline)
    spec_lock = spec_lock_path.read_text(encoding="utf-8")

    for index, slide in enumerate(deck_outline, start=1):
        page = _safe_page(slide.get("page", index), index)
        title = slide.get("title", "")
        file_name = f"P{page:02d}_{_slug(title)}.svg"
        svg_path = svg_output_dir / file_name

        print(f"Agent：正在生成 SVG 第 {page}/{total} 页：{title}")

        try:
            res = llm.invoke(
                [
                    SystemMessage(
                        content="""
你是一个 PPT SVG 页面生成助手。

你需要生成一页 16:9 PPT SVG。

要求：
1. 只输出 SVG 代码，不要解释。
2. viewBox 必须是 0 0 1280 720。
3. 不要使用 <style>、class、foreignObject、script、iframe、animate、symbol、use。
4. 文字必须直接写在 <text> 元素里。
5. 使用绝对坐标布局。
"""
                    ),
                    HumanMessage(
                        content=f"""
请生成这一页 PPT 的 SVG。

PPT Brief:
{ppt_brief}

spec_lock.md:
{spec_lock}

当前页:
{slide}
"""
                    ),
                ]
            )

            svg = _clean_svg(res.content)
            if not svg.lstrip().startswith("<svg"):
                raise ValueError("LLM 没有返回 SVG 代码")

            svg_path.write_text(svg, encoding="utf-8")
            generated_files.append(str(svg_path))
        except Exception as exc:
            return {
                "status": "failed",
                "error": f"第 {page} 页 SVG 生成失败：{exc}",
            }

        print(f"Agent：SVG 第 {page}/{total} 页已生成：{svg_path}")

    return {
        "status": "svg_created",
        "svg_files": generated_files,
        "assistant_reply": f"已生成 {len(generated_files)} 页 SVG。",
    }


def _slug(text: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9]+", "_", str(text)).strip("_").lower()
    if not name:
        return "slide"
    return name


def _safe_page(page, default: int) -> int:
    match = re.search(r"\d+", str(page))

    if match:
        return int(match.group())

    return default


def _clean_svg(text: str) -> str:
    value = text.strip()

    if value.startswith("```"):
        value = re.sub(r"^```[a-zA-Z]*", "", value).strip()
        value = re.sub(r"```$", "", value).strip()

    return value
