import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


SUPPORTED_SUFFIXES = {".txt", ".md", ".markdown"}
# 扩展支持：通过 ppt_creator 解析器转换的格式
CONVERTIBLE_SUFFIXES = {
    ".pdf", ".docx", ".doc", ".odt", ".rtf",
    ".xlsx", ".xlsm",
    ".pptx", ".pptm", ".ppsx",
    ".epub", ".html", ".htm",
    ".tex", ".latex", ".rst", ".org", ".typ",
    ".ipynb",
}
MAX_FILE_BYTES = 20 * 1024 * 1024  # 20MB 上限

PPT_CREATOR_ROOT = Path(__file__).resolve().parents[2] / "ppt_creator"


@dataclass(frozen=True)
class UploadedMaterial:
    filename: str
    text: str
    converted: bool = False  # True if was parsed from non-text format


def decode_material_bytes(filename: str, content: bytes) -> UploadedMaterial:
    """Decode an uploaded material file, supporting multiple formats."""
    suffix = _suffix(filename)
    all_supported = SUPPORTED_SUFFIXES | CONVERTIBLE_SUFFIXES

    if suffix not in all_supported:
        supported = ", ".join(sorted(all_supported))
        raise ValueError(f"仅支持 {supported} 格式的资料文件。")

    if len(content) > MAX_FILE_BYTES:
        raise ValueError("单个资料文件不能超过 20MB。")

    # 文本格式直接解码
    if suffix in SUPPORTED_SUFFIXES:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            text = content.decode("gbk")

        text = text.strip()
        if not text:
            raise ValueError("资料文件内容不能为空。")

        return UploadedMaterial(filename=filename, text=text, converted=False)

    # 非文本格式 → 调用 ppt_creator 解析器转换
    text = _convert_document(filename, content, suffix)
    if not text.strip():
        raise ValueError(f"无法解析 {filename} 的内容。")

    return UploadedMaterial(filename=filename, text=text.strip(), converted=True)


def _convert_document(filename: str, content: bytes, suffix: str) -> str:
    """使用 ppt_creator 的解析器将非文本文件转为 Markdown 文本。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir) / filename
        tmp_path.write_bytes(content)

        parser_script = _resolve_parser(suffix)
        if not parser_script:
            raise ValueError(f"不支持的文件格式：{suffix}")

        output_path = tmp_path.with_suffix(".md")
        try:
            result = subprocess.run(
                [sys.executable, str(parser_script), str(tmp_path), "-o", str(output_path)],
                cwd=PPT_CREATOR_ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=120,
            )
        except subprocess.TimeoutExpired:
            raise ValueError(f"文件解析超时：{filename}")
        except Exception as exc:
            raise ValueError(f"文件解析失败：{filename} → {exc}")

        if not output_path.exists():
            # 尝试父目录（部分解析器在同目录生成）
            output_path = tmp_path.parent / f"{tmp_path.stem}.md"

        if output_path.exists():
            return output_path.read_text(encoding="utf-8", errors="replace")

        # 如果解析器没生成 md 文件，回退 stdout
        if result.stdout.strip():
            return result.stdout.strip()

        raise ValueError(
            f"文件解析失败：{filename}\n{result.stderr or result.stdout or '无输出'}"
        )


def _resolve_parser(suffix: str) -> Path | None:
    """根据文件后缀返回对应的解析器脚本路径。"""
    script_dir = PPT_CREATOR_ROOT / "skills" / "ppt-master" / "scripts" / "source_to_md"

    parser_map = {
        ".pdf": "pdf_to_md.py",
        ".docx": "doc_to_md.py",
        ".doc": "doc_to_md.py",
        ".odt": "doc_to_md.py",
        ".rtf": "doc_to_md.py",
        ".epub": "doc_to_md.py",
        ".html": "doc_to_md.py",
        ".htm": "doc_to_md.py",
        ".tex": "doc_to_md.py",
        ".latex": "doc_to_md.py",
        ".rst": "doc_to_md.py",
        ".org": "doc_to_md.py",
        ".typ": "doc_to_md.py",
        ".ipynb": "doc_to_md.py",
        ".xlsx": "excel_to_md.py",
        ".xlsm": "excel_to_md.py",
        ".pptx": "ppt_to_md.py",
        ".pptm": "ppt_to_md.py",
        ".ppsx": "ppt_to_md.py",
    }

    script_name = parser_map.get(suffix)
    if not script_name:
        return None

    script_path = script_dir / script_name
    return script_path if script_path.exists() else None


def summarize_materials(raw_texts: list[str]) -> dict:
    """Build a small deterministic summary for uploaded materials."""
    joined = "\n\n".join(raw_texts)
    keywords = _extract_keywords(joined)
    topic = _extract_topic(joined, keywords)
    key_points = _extract_key_points(joined, keywords)

    return {
        "topic": topic,
        "keywords": keywords,
        "key_points": key_points,
        "summary": joined[:1200],
    }


def _suffix(filename: str) -> str:
    match = re.search(r"(\.[^.]+)$", filename.lower())
    return match.group(1) if match else ""


def _extract_keywords(text: str) -> list[str]:
    match = re.search(r"(?:关键词|keywords?)[:：]\s*(.+)", text, re.I)
    if not match:
        return []

    parts = re.split(r"[；;，,\s]+", match.group(1).strip())
    return [part.strip() for part in parts if part.strip()][:12]


def _extract_topic(text: str, keywords: list[str]) -> str:
    patterns = [
        r"(?:论文题目|题目|title)[:：]\s*(.+)",
        r"^#\s+(.+)$",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.I | re.M)
        if match:
            return match.group(1).strip(" ，,。；;#")[:80]

    if keywords:
        return "、".join(keywords[:3]) + "相关内容"

    for line in text.splitlines():
        value = line.strip(" ：:，,。；;#")
        if value:
            return value[:80]

    return ""


def _extract_key_points(text: str, keywords: list[str]) -> list[str]:
    key_points = []
    if keywords:
        key_points.append("关键词：" + "、".join(keywords))

    headings = re.findall(r"^(?:#{1,3}\s+.+|\d+(?:\.\d+)*\s+.+)$", text, re.M)
    for heading in headings[:10]:
        key_points.append(heading.strip(" #")[:120])

    return key_points
