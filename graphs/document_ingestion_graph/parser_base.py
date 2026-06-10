from dataclasses import dataclass, field


@dataclass
class ParsedSection:
    heading_path: str
    text: str
    heading_level: int = 1
    page_start: int | None = None
    page_end: int | None = None
    content_type: str = "text"
    metadata: dict = field(default_factory=dict)


@dataclass
class ParsedDocument:
    title: str
    source_path: str
    raw_text: str
    normalized_markdown: str
    sections: list[ParsedSection]
    metadata: dict = field(default_factory=dict)


@dataclass
class Chunk:
    chunk_id: str
    chunk_index: int
    content: str
    content_type: str = "text"
    heading_path: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    token_count: int = 0
    keywords: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
