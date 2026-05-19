from rag.ingestors.base import FileIngestor, WebIngestor, ParsedSegment
from rag.ingestors.csv import CsvIngestor
from rag.ingestors.docx import DocxIngestor
from rag.ingestors.pdf import PdfIngestor
from rag.ingestors.text import MarkdownIngestor, TextIngestor
from rag.ingestors.web import HttpWebIngestor
from rag.ingestors.xlsx import XlsxIngestor


_FILE_INGESTORS: tuple[FileIngestor, ...] = (
    PdfIngestor(),
    DocxIngestor(),
    XlsxIngestor(),
    CsvIngestor(),
    MarkdownIngestor(),
    TextIngestor(),
)

_REGISTRY: dict[str, FileIngestor] = {
    ext: ing for ing in _FILE_INGESTORS for ext in ing.extensions
}

SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(_REGISTRY.keys())


def get_file_ingestor(ext: str) -> FileIngestor:
    ing = _REGISTRY.get(ext.lower())
    if ing is None:
        raise ValueError(f"Unsupported file extension: {ext or '(none)'}")
    return ing


__all__ = [
    "FileIngestor",
    "WebIngestor",
    "ParsedSegment",
    "PdfIngestor",
    "DocxIngestor",
    "XlsxIngestor",
    "CsvIngestor",
    "MarkdownIngestor",
    "TextIngestor",
    "HttpWebIngestor",
    "SUPPORTED_EXTENSIONS",
    "get_file_ingestor",
]
