from pathlib import Path
from typing import Protocol

from core.ingestion.parser_base import ParsedDocument


class DocumentParser(Protocol):
    supported_extensions: set[str]
    def parse(self, path: Path) -> ParsedDocument: ...
