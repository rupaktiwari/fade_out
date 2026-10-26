import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

from app.core.config import settings

COLLECTION_NAME = "documents"
VECTOR_SIZE = 384  # output size of the embedding model above

client = QdrantClient(url=settings.qdrant_url)


def ensure_collection() -> None:
    """Create the Qdrant collection on startup, if it doesn't already exist."""
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME not in existing:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )


def upsert_chunks(document_id: int, filename: str, chunks: list[str], embeddings: list[list[float]]) -> None:
    """Save each chunk's embedding, tagged with which document and chunk index it came from."""
    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=embedding,
            payload={
                "document_id": document_id,
                "filename": filename,
                "chunk_index": i,
                "text": chunk,
            },
        )
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings))
    ]
    client.upsert(collection_name=COLLECTION_NAME, points=points)


def search(query_embedding: list[float], top_k: int = 3) -> list[str]:
    results = client.query_points(collection_name=COLLECTION_NAME, query=query_embedding, limit=top_k)
    return [point.payload["text"] for point in results.points]