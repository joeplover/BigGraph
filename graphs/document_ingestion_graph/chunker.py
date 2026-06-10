from uuid import uuid4

from config.settings import settings
from graphs.document_ingestion_graph.cleaner import TextCleaner
from graphs.document_ingestion_graph.parser_base import Chunk, ParsedDocument, ParsedSection
from graphs.document_ingestion_graph.tokenizer import ChineseTokenizer

class StructureAwareChunker:
    def __init__(self, chunk_size: int | None = None, chunk_overlap: int | None = None) -> None:
        self.chunk_size = max(50, chunk_size or settings.CHUNK_SIZE)
        self.chunk_overlap = max(0, min(chunk_overlap or settings.CHUNK_OVERLAP, self.chunk_size // 2))
        self.cleaner = TextCleaner()
        self.tokenizer = ChineseTokenizer()

    def chunk(self, parsed: ParsedDocument) -> list[Chunk]:
        chunks: list[Chunk] = []
        for section in parsed.sections:
            chunks.extend(self._chunk_section(section, start_index=len(chunks)))
        return chunks

    def _chunk_section(self, section: ParsedSection, start_index: int) -> list[Chunk]:
        cleaned = self.cleaner.clean(section.text)
        if not cleaned:
            return []
        if section.content_type == "table":
            return [self._make_chunk(start_index, self._with_heading(section.heading_path, cleaned), section, "table")]
        paragraphs = [p.strip() for p in cleaned.split("\n\n") if p.strip()]
        if not paragraphs:
            return []
        result: list[Chunk] = []
        buffer = ""
        for para in paragraphs:
            candidate = para if not buffer else buffer + "\n\n" + para
            if len(candidate) <= self.chunk_size:
                buffer = candidate
                continue
            if buffer:
                result.append(self._make_chunk(start_index + len(result), self._with_heading(section.heading_path, buffer), section, "text"))
                buffer = self._tail_overlap(buffer)
            if len(para) > self.chunk_size:
                result.extend(self._hard_split(para, section, start_index + len(result)))
                buffer = ""
            else:
                buffer = para
        if buffer:
            result.append(self._make_chunk(start_index + len(result), self._with_heading(section.heading_path, buffer), section, "text"))
        return result

    def _hard_split(self, text: str, section: ParsedSection, start_index: int) -> list[Chunk]:
        chunks: list[Chunk] = []
        step = max(1, self.chunk_size - self.chunk_overlap)
        for offset in range(0, len(text), step):
            part = text[offset:offset + self.chunk_size]
            if part.strip():
                chunks.append(self._make_chunk(start_index + len(chunks), self._with_heading(section.heading_path, part), section, "text"))
        return chunks

    def _tail_overlap(self, text: str) -> str:
        if self.chunk_overlap <= 0 or not text:
            return ""
        return text[-self.chunk_overlap:]

    def _with_heading(self, heading_path: str, text: str) -> str:
        if not heading_path:
            return text
        return f"标题路径：{heading_path}\n\n正文：\n{text}".strip()

    def _make_chunk(self, index: int, text: str, section: ParsedSection, content_type: str) -> Chunk:
        keywords = self.tokenizer.keywords(text)
        return Chunk(
            chunk_id=str(uuid4()), chunk_index=index, content=text, content_type=content_type,
            heading_path=section.heading_path, page_start=section.page_start, page_end=section.page_end,
            token_count=len(text), keywords=keywords, metadata=section.metadata,
        )
