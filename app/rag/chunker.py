import io
from pypdf import PdfReader


def chunk_text(text: str, source: str, size: int = 500, overlap: int = 60) -> list[dict]:
    chunks = []
    start = 0
    chunk_idx = 0
    while start < len(text):
        chunk = text[start:start + size].strip()
        if chunk:
            chunks.append({"source": source, "page": 1, "chunk": chunk_idx, "text": chunk})
            chunk_idx += 1
        start += size - overlap
    return chunks


def chunk_pdf(content: bytes, filename: str, size: int = 500, overlap: int = 60) -> list[dict]:
    reader = PdfReader(io.BytesIO(content))
    chunks = []

    for page_num, page in enumerate(reader.pages):
        text = (page.extract_text() or "").strip()
        if not text:
            continue

        start = 0
        chunk_idx = 0
        while start < len(text):
            end = start + size
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append({
                    "source": filename,
                    "page": page_num + 1,
                    "chunk": chunk_idx,
                    "text": chunk_text,
                })
                chunk_idx += 1
            start += size - overlap

    return chunks
