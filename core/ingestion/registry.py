from pathlib import Path
from typing import Protocol

from core.ingestion.parser_base import ParsedDocument
from core.ingestion.parsers.csv import CsvParser
from core.ingestion.parsers.docx import DocxParser
from core.ingestion.parsers.excel import ExcelParser
from core.ingestion.parsers.html import HtmlParser
from core.ingestion.parsers.markdown import MarkdownParser
from core.ingestion.parsers.pdf import PdfParser
from core.ingestion.parsers.txt import TxtParser


class DocumentParser(Protocol):
    supported_extensions: set[str]
    def parse(self, path: Path) -> ParsedDocument: ...


class ParserRegistry:
    def __init__(self) -> None:
        self._parsers: list[DocumentParser] = [
            TxtParser(), MarkdownParser(), PdfParser(), DocxParser(),
            CsvParser(), ExcelParser(), HtmlParser(),
        ]

    def get_parser(self, path: Path) -> DocumentParser:
        suffix = path.suffix.lower()
        for parser in self._parsers:
            if suffix in parser.supported_extensions:
                return parser
        raise ValueError(f"不支持的格式: {suffix}，当前支持: txt / md / pdf / docx / csv / xlsx / html")
