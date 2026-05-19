import io
from typing import Iterable

from pypdf import PdfReader

from rag.document_model import DocType
from rag.ingestors.base import FileIngestor, ParsedSegment


class PdfIngestor(FileIngestor):
    extensions = (".pdf",)
    doc_type = DocType.pdf

    def parse(self, content: bytes, filename: str) -> Iterable[ParsedSegment]:
        reader = PdfReader(io.BytesIO(content))
        for page_num, page in enumerate(reader.pages):
            text = (page.extract_text() or "").strip()
            if text:
                yield ParsedSegment(source=filename, page=page_num + 1, text=text)
