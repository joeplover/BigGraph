from pathlib import Path
from graphs.document_ingestion_graph.parser_base import ParsedDocument, ParsedSection


class TxtParser:
    supported_extensions = {".txt"}
    def parse(self, path: Path) -> ParsedDocument:
        text = path.read_text(encoding="utf-8", errors="ignore")
        return ParsedDocument(title=path.stem, source_path=str(path), raw_text=text, normalized_markdown=text, sections=[ParsedSection(heading_path=path.stem, text=text)], metadata={"parser": "txt"})
