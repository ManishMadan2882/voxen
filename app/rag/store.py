import logging
import os
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue, MatchAny

COLLECTION = "knowledge"
VECTOR_SIZE = 768  # nomic-embed-text

logger = logging.getLogger(__name__)

_client: QdrantClient | None = None


def get_client() -> QdrantClient:
    global _client
    if _client is not None:
        return _client

    url = os.getenv("QDRANT_URL")
    api_key = os.getenv("QDRANT_API_KEY")
    path = os.getenv("QDRANT_PATH")

    # Priority: remote URL > on-disk path > in-memory (non-persistent, dev only)
    if url:
        _client = QdrantClient(url=url, api_key=api_key)
    elif path:
        _client = QdrantClient(path=path)
    else:
        logger.warning(
            "Qdrant running in-memory; data is lost on restart. "
            "Set QDRANT_URL or QDRANT_PATH to persist."
        )
        _client = QdrantClient(":memory:")

    if not _client.collection_exists(COLLECTION):
        _client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )

    return _client


def upsert(points: list[PointStruct]) -> None:
    get_client().upsert(collection_name=COLLECTION, points=points)


def search(
    vector: list[float],
    limit: int = 4,
    score_threshold: float = 0.55,
    id_filters: list[str] | None = None,
) -> list[dict]:
    flt = (
        Filter(must=[FieldCondition(key="doc_id", match=MatchAny(any=id_filters))])
        if id_filters else None
    )
    response = get_client().query_points(
        collection_name=COLLECTION,
        query=vector,
        query_filter=flt,
        limit=limit,
        score_threshold=score_threshold,
        with_payload=True,
    )
    hits = [{"score": round(r.score, 3), **r.payload} for r in response.points]

    logger.info(
        "RAG search: limit=%d threshold=%.2f id_filters=%s -> %d hit(s)",
        limit, score_threshold, id_filters, len(hits),
    )
    # per-doc tally to surface single-doc bias when filters span multiple docs
    per_doc: dict[str, int] = {}
    for h in hits:
        per_doc[h.get("doc_id", "?")] = per_doc.get(h.get("doc_id", "?"), 0) + 1
    if per_doc:
        logger.info("RAG hits by doc_id: %s", per_doc)
    for i, h in enumerate(hits):
        snippet = (h.get("text") or "").replace("\n", " ")[:120]
        logger.info(
            "  #%d score=%.3f doc_id=%s source=%s page=%s | %s",
            i, h["score"], h.get("doc_id"), h.get("source"), h.get("page"), snippet,
        )

    if not hits:
        _diagnose_empty(vector, id_filters, score_threshold, limit)
    return hits


def _diagnose_empty(
    vector: list[float],
    id_filters: list[str] | None,
    score_threshold: float,
    limit: int,
) -> None:
    """When a filtered query yields nothing, log enough to tell why:
    are matching points missing, is the filter pruning HNSW, or is the
    semantic similarity simply too low?"""
    client = get_client()
    try:
        unfiltered = client.query_points(
            collection_name=COLLECTION,
            query=vector,
            limit=max(limit, 5),
            with_payload=True,
        ).points
        logger.info(
            "RAG diag: unfiltered top scores=%s doc_ids=%s",
            [round(p.score, 3) for p in unfiltered],
            [p.payload.get("doc_id") for p in unfiltered],
        )
    except Exception:
        logger.exception("RAG diag: unfiltered preview failed")

    if not id_filters:
        return
    try:
        flt = Filter(must=[FieldCondition(key="doc_id", match=MatchAny(any=id_filters))])
        present, _ = client.scroll(
            collection_name=COLLECTION,
            scroll_filter=flt,
            limit=1000,
            with_payload=["doc_id"],
            with_vectors=False,
        )
        counts: dict[str, int] = {}
        for p in present:
            did = p.payload.get("doc_id", "?")
            counts[did] = counts.get(did, 0) + 1
        logger.info(
            "RAG diag: points present for filtered doc_ids=%s threshold=%.2f",
            counts, score_threshold,
        )
    except Exception:
        logger.exception("RAG diag: filtered scroll failed")


def list_sources() -> list[dict]:
    client = get_client()
    try:
        points, _ = client.scroll(
            collection_name=COLLECTION,
            limit=10_000,
            with_payload=True,
            with_vectors=False,
        )
    except Exception:
        return []

    counts: dict[str, int] = {}
    for p in points:
        src = p.payload.get("source", "unknown")
        counts[src] = counts.get(src, 0) + 1

    return [{"file": k, "chunks": v} for k, v in counts.items()]
