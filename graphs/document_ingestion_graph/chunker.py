from uuid import uuid4

import re

from config.settings import settings
from graphs.document_ingestion_graph.cleaner import TextCleaner
from graphs.document_ingestion_graph.parser_base import Chunk, ParsedDocument, ParsedSection
from graphs.document_ingestion_graph.tokenizer import ChineseTokenizer


# 中英文句子结束符
_SENTENCE_END = re.compile(r"([。！？\.!?…])")


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
            # 如果段落本身超过 chunk_size，先尝试按句子拆分
            if len(para) > self.chunk_size:
                # 先把当前 buffer 落盘
                if buffer:
                    result.append(self._make_chunk(start_index + len(result), self._with_heading(section.heading_path, buffer), section, "text"))
                    buffer = self._tail_overlap(buffer)
                # 按句子拆分这个长段落
                sentences = self._split_sentences(para)
                for sent in sentences:
                    if not buffer:
                        buffer = sent
                    elif len(buffer) + len(sent) + 2 <= self.chunk_size:
                        buffer += sent
                    else:
                        result.append(self._make_chunk(start_index + len(result), self._with_heading(section.heading_path, buffer), section, "text"))
                        buffer = self._tail_overlap(buffer)
                        buffer = sent
                # buffer 里可能还剩一些句子，交给下面的收尾逻辑处理
                continue

            # 正常段落，装到 buffer 里
            candidate = para if not buffer else buffer + "\n\n" + para
            if len(candidate) <= self.chunk_size:
                buffer = candidate
                continue
            # buffer 满了，落盘
            result.append(self._make_chunk(start_index + len(result), self._with_heading(section.heading_path, buffer), section, "text"))
            buffer = self._tail_overlap(buffer)
            buffer = para

        # 收尾 buffer
        if buffer:
            result.append(self._make_chunk(start_index + len(result), self._with_heading(section.heading_path, buffer), section, "text"))
        return result

    def _split_sentences(self, text: str) -> list[str]:
        """按句子结束符拆分文本，保留分隔符在句子末尾。"""
        # 用零宽断言在句子结束符后拆分
        parts = _SENTENCE_END.split(text)
        sentences = []
        buf = ""
        for i, part in enumerate(parts):
            buf += part
            # 如果当前部分是句子结束符，或已经到了末尾
            if _SENTENCE_END.fullmatch(part) or i == len(parts) - 1:
                if buf.strip():
                    sentences.append(buf.strip())
                buf = ""
        # 如果某些部分被 split 打散导致 buf 里还有内容
        if buf.strip():
            sentences.append(buf.strip())
        # 空安全过滤
        return [s for s in sentences if s]

    def _hard_split(self, text: str, section: ParsedSection, start_index: int) -> list[Chunk]:
        """退避策略：在句子边界切分，尽可能避免断在句子中间。"""
        sentences = self._split_sentences(text)
        if len(sentences) <= 1:
            # 连句子拆分都做不到（无标点的连续文本），只能硬切字符
            chunks: list[Chunk] = []
            step = max(1, self.chunk_size - self.chunk_overlap)
            for offset in range(0, len(text), step):
                part = text[offset:offset + self.chunk_size]
                if part.strip():
                    chunks.append(self._make_chunk(start_index + len(chunks), self._with_heading(section.heading_path, part), section, "text"))
            return chunks

        chunks: list[Chunk] = []
        buffer = ""
        for sent in sentences:
            candidate = sent if not buffer else buffer + sent
            if len(candidate) <= self.chunk_size:
                buffer = candidate
            else:
                if buffer:
                    chunks.append(self._make_chunk(start_index + len(chunks), self._with_heading(section.heading_path, buffer), section, "text"))
                buffer = sent
        if buffer:
            chunks.append(self._make_chunk(start_index + len(chunks), self._with_heading(section.heading_path, buffer), section, "text"))
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
