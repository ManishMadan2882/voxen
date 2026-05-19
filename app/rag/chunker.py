def split_text(text: str, source: str, page: int, size: int, overlap: int) -> list[dict]:
    out: list[dict] = []
    start = 0
    chunk_idx = 0
    while start < len(text):
        chunk = text[start:start + size].strip()
        if chunk:
            out.append({"source": source, "page": page, "chunk": chunk_idx, "text": chunk})
            chunk_idx += 1
        start += size - overlap
    return out


def chunk_text(text: str, source: str, size: int = 500, overlap: int = 60) -> list[dict]:
    return split_text(text, source, page=1, size=size, overlap=overlap)
