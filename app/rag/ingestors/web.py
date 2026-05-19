import httpx
from bs4 import BeautifulSoup

from rag.chunker import split_text
from rag.ingestors.base import WebIngestor
from rag.ingestors.pdf import PdfIngestor


class HttpWebIngestor(WebIngestor):
    """Fetch a URL over HTTP(S) and chunk its readable content."""

    user_agent = "VoxenBot/1.0 (+knowledge-base ingestion)"

    def ingest(
        self, url: str, size: int = 500, overlap: int = 60, timeout: float = 20.0
    ) -> tuple[list[dict], str]:
        with httpx.Client(
            follow_redirects=True, timeout=timeout, headers={"User-Agent": self.user_agent}
        ) as client:
            resp = client.get(url)
            resp.raise_for_status()
            ctype = resp.headers.get("content-type", "").lower()
            body = resp.content
            encoding = resp.encoding or "utf-8"

        if "html" in ctype or ctype == "":
            return self._ingest_html(body, url, size, overlap)
        if "pdf" in ctype:
            return PdfIngestor().ingest(body, url, size, overlap), url

        text = body.decode(encoding, errors="replace").strip()
        if not text:
            return [], url
        return split_text(text, url, page=1, size=size, overlap=overlap), url

    def _ingest_html(
        self, body: bytes, url: str, size: int, overlap: int
    ) -> tuple[list[dict], str]:
        soup = BeautifulSoup(body, "html.parser")
        title = soup.title.string.strip() if soup.title and soup.title.string else url
        for tag in soup(["script", "style", "noscript", "header", "footer", "nav", "aside"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        if not text:
            return [], title
        return split_text(text, title, page=1, size=size, overlap=overlap), title
