from pathlib import Path
from typing import Protocol

from graphs.document_ingestion_graph.parser_base import ParsedDocument
from graphs.document_ingestion_graph.parsers.csv import CsvParser
from graphs.document_ingestion_graph.parsers.docx import DocxParser
from graphs.document_ingestion_graph.parsers.excel import ExcelParser
from graphs.document_ingestion_graph.parsers.html import HtmlParser
from graphs.document_ingestion_graph.parsers.markdown import MarkdownParser
from graphs.document_ingestion_graph.parsers.pdf import PdfParser
from graphs.document_ingestion_graph.parsers.txt import TxtParser


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
