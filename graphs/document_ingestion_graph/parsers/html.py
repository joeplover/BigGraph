from pathlib import Path
from bs4 import BeautifulSoup
from graphs.document_ingestion_graph.parser_base import ParsedDocument, ParsedSection


class HtmlParser:
    supported_extensions = {".html", ".htm"}
    def parse(self, path: Path) -> ParsedDocument:
        html = path.read_text(encoding="utf-8", errors="ignore")
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript", "iframe", "nav", "footer"]):
            tag.decompose()
        title = soup.title.text.strip() if soup.title and soup.title.text else path.stem
        text = soup.get_text("\n")
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        normalized = "\n".join(lines)
        return ParsedDocument(title=title, source_path=str(path), raw_text=text, normalized_markdown=normalized, sections=[ParsedSection(heading_path=title, text=normalized)], metadata={"parser": "html"})
