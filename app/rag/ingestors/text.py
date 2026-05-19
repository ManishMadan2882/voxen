from typing import Iterable

from rag.document_model import DocType
from rag.ingestors.base import FileIngestor, ParsedSegment


class _PlainBytesIngestor(FileIngestor):
    def parse(self, content: bytes, filename: str) -> Iterable[ParsedSegment]:
        text = content.decode("utf-8", errors="replace").strip()
        if text:
            yield ParsedSegment(source=filename, page=1, text=text)


class MarkdownIngestor(_PlainBytesIngestor):
    extensions = (".md", ".markdown")
    doc_type = DocType.markdown


class TextIngestor(_PlainBytesIngestor):
    extensions = (".txt",)
    doc_type = DocType.text
