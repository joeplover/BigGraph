from pathlib import Path
from core.ingestion.parser_base import ParsedDocument, ParsedSection


class MarkdownParser:
    supported_extensions = {".md", ".markdown"}
    def parse(self, path: Path) -> ParsedDocument:
        text = path.read_text(encoding="utf-8", errors="ignore")
        sections, cur, level, buf = [], path.stem, 1, []
        for line in text.splitlines():
            s = line.strip()
            if s.startswith("#"):
                if buf:
                    sections.append(ParsedSection(heading_path=cur, heading_level=level, text="\n".join(buf).strip()))
                    buf = []
                lv = len(s) - len(s.lstrip("#"))
                title = s.lstrip("#").strip()
                cur = f"{path.stem} / {title}" if title else path.stem
                level = lv if lv > 0 else 1
            else:
                buf.append(line)
        if buf:
            sections.append(ParsedSection(heading_path=cur, heading_level=level, text="\n".join(buf).strip()))
        if not sections:
            sections = [ParsedSection(heading_path=path.stem, text=text)]
        return ParsedDocument(title=path.stem, source_path=str(path), raw_text=text, normalized_markdown=text, sections=sections, metadata={"parser": "markdown"})
