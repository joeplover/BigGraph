from pathlib import Path
import fitz
from core.ingestion.parser_base import ParsedDocument, ParsedSection


class PdfParser:
    supported_extensions = {".pdf"}
    def parse(self, path: Path) -> ParsedDocument:
        doc = fitz.open(str(path))
        sections, pages = [], []
        try:
            for i, page in enumerate(doc, start=1):
                text = page.get_text("text") or ""
                pages.append(text)
                if text.strip():
                    sections.append(ParsedSection(heading_path=f"{path.stem} / 第{i}页", text=text, page_start=i, page_end=i))
            raw = "\n\n".join(pages)
            return ParsedDocument(title=path.stem, source_path=str(path), raw_text=raw, normalized_markdown=raw, sections=sections, metadata={"parser": "pdf", "page_count": len(doc)})
        finally:
            doc.close()
