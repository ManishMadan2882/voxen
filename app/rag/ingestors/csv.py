import csv as _csv
import io
from typing import Iterable

from rag.document_model import DocType
from rag.ingestors.base import FileIngestor, ParsedSegment


class CsvIngestor(FileIngestor):
    extensions = (".csv",)
    doc_type = DocType.csv

    def parse(self, content: bytes, filename: str) -> Iterable[ParsedSegment]:
        decoded = content.decode("utf-8", errors="replace")
        reader = _csv.reader(io.StringIO(decoded))
        rows = [
            " | ".join(cell.strip() for cell in row)
            for row in reader
            if any(c.strip() for c in row)
        ]
        text = "\n".join(rows).strip()
        if text:
            yield ParsedSegment(source=filename, page=1, text=text)
