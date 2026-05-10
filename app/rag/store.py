import os
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue, MatchAny

COLLECTION = "knowledge"
VECTOR_SIZE = 768  # nomic-embed-text

_client: QdrantClient | None = None


def get_client() -> QdrantClient:
    global _client
    if _client is not None:
        return _client

    url = os.getenv("QDRANT_URL")
    api_key = os.getenv("QDRANT_API_KEY")

    # In-memory for dev; set QDRANT_URL for cloud/prod
    _client = QdrantClient(url=url, api_key=api_key) if url else QdrantClient(":memory:")

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
    source_filters: list[str] | None = None,
) -> list[dict]:
    flt = (
        Filter(must=[FieldCondition(key="source", match=MatchAny(any=source_filters))])
        if source_filters else None
    )
    results = get_client().search(
        collection_name=COLLECTION,
        query_vector=vector,
        query_filter=flt,
        limit=limit,
        score_threshold=score_threshold,
        with_payload=True,
    )
    return [{"score": round(r.score, 3), **r.payload} for r in results]


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
