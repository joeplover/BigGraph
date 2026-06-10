import csv
from pathlib import Path
from graphs.document_ingestion_graph.parser_base import ParsedDocument, ParsedSection


class CsvParser:
    supported_extensions = {".csv"}
    def parse(self, path: Path) -> ParsedDocument:
        with open(path, encoding="utf-8-sig", errors="ignore") as f:
            rows = list(csv.reader(f))
        if not rows:
            return ParsedDocument(title=path.stem, source_path=str(path), raw_text="", normalized_markdown="", sections=[ParsedSection(heading_path=path.stem, text="")], metadata={"parser": "csv", "rows": 0})
        cols = max(len(r) for r in rows)
        md = "| " + " | ".join(rows[0]) + " |\n"
        md += "| " + " | ".join(["---"] * cols) + " |\n"
        for r in rows[1:]:
            md += "| " + " | ".join(r + [""] * (cols - len(r))) + " |\n"
        raw = "\n".join([",".join(r) for r in rows])
        return ParsedDocument(title=path.stem, source_path=str(path), raw_text=raw, normalized_markdown=md, sections=[ParsedSection(heading_path=path.stem, text=md, content_type="table", metadata={"row_count": len(rows) - 1, "col_count": cols})], metadata={"parser": "csv", "rows": len(rows) - 1})
