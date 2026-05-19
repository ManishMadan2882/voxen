from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterable

from rag.chunker import split_text
from rag.document_model import DocType


@dataclass(frozen=True)
class ParsedSegment:
    source: str
    page: int
    text: str


class FileIngestor(ABC):
    """Parse a binary file payload into segments and chunk them."""

    extensions: tuple[str, ...] = ()
    doc_type: DocType = DocType.text

    @abstractmethod
    def parse(self, content: bytes, filename: str) -> Iterable[ParsedSegment]:
        ...

    def ingest(
        self, content: bytes, filename: str, size: int = 500, overlap: int = 60
    ) -> list[dict]:
        chunks: list[dict] = []
        for seg in self.parse(content, filename):
            text = seg.text.strip()
            if not text:
                continue
            chunks.extend(split_text(text, seg.source, page=seg.page, size=size, overlap=overlap))
        return chunks


class WebIngestor(ABC):
    """Fetch a remote resource and chunk its readable content."""

    doc_type: DocType = DocType.url

    @abstractmethod
    def ingest(
        self, url: str, size: int = 500, overlap: int = 60, timeout: float = 20.0
    ) -> tuple[list[dict], str]:
        """Returns (chunks, page_title_or_url)."""
