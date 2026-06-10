from pathlib import Path
from typing import Protocol

from graphs.document_ingestion_graph.parser_base import ParsedDocument


class DocumentParser(Protocol):
    supported_extensions: set[str]
    def parse(self, path: Path) -> ParsedDocument: ...
