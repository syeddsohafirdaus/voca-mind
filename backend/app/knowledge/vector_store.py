import uuid
from typing import Any, Dict, List, Optional
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from app.config import settings
from app.knowledge.collection import ensure_collection
from app.knowledge.schemas import ChunkMetadata, KnowledgeChunk, SourceType
from app.logger import logger

# Namespace UUID for deterministic Qdrant point IDs from chunk_ids
QDRANT_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


class QdrantVectorStore:
    """Abstraction for managing vector storage and similarity search in Qdrant.

    Preserves source document provenance within payloads.
    MUST NOT store user IDs, conversation data, or patient records.
    """

    def __init__(
        self,
        client: Optional[Any] = None,
        url: str = settings.QDRANT_URL,
        api_key: Optional[str] = settings.QDRANT_API_KEY,
        collection_name: str = settings.QDRANT_COLLECTION_NAME,
        dimension: int = settings.EMBEDDING_DIMENSION,
    ) -> None:
        self.url = url
        self.api_key = api_key
        self.collection_name = collection_name
        self.dimension = dimension

        if client is not None:
            self.client = client
        else:
            self.client = QdrantClient(url=self.url, api_key=self.api_key)

    def initialize(self) -> bool:
        """Ensures Qdrant collection exists with proper dimensions and metrics."""
        return ensure_collection(
            client=self.client,
            collection_name=self.collection_name,
            dimension=self.dimension,
            distance="Cosine",
        )

    def _chunk_id_to_uuid(self, chunk_id: str) -> str:
        """Deterministically generates a UUID v5 string from chunk_id for Qdrant point ID."""
        return str(uuid.uuid5(QDRANT_NAMESPACE, chunk_id))

    def upsert_chunks(
        self,
        chunks: List[KnowledgeChunk],
        vectors: List[List[float]],
    ) -> int:
        """Upserts a list of KnowledgeChunk items and matching vectors into Qdrant.

        Preserves source provenance payload. Returns count of upserted points.
        Raises ValueError if counts do not match or input is invalid.
        """
        if len(chunks) != len(vectors):
            raise ValueError(f"Chunks count ({len(chunks)}) must match vectors count ({len(vectors)}).")
        if not chunks:
            return 0

        self.initialize()
        points = []

        for chunk, vector in zip(chunks, vectors):
            if len(vector) != self.dimension:
                raise ValueError(
                    f"Vector dimension ({len(vector)}) does not match store dimension ({self.dimension})."
                )

            point_id = self._chunk_id_to_uuid(chunk.chunk_id)

            payload: Dict[str, Any] = {
                "document_id": chunk.document_id,
                "chunk_id": chunk.chunk_id,
                "chunk_index": chunk.chunk_index,
                "text": chunk.text,
                "title": chunk.title,
                "source_name": chunk.source_name,
                "source_url": str(chunk.source_url),
                "topic": chunk.topic,
                "language": chunk.language,
                "source_type": chunk.metadata.source_type.value,
                "publisher": chunk.metadata.publisher,
                "version": chunk.metadata.version,
                "reviewed": chunk.metadata.reviewed,
                "total_chunks": chunk.metadata.total_chunks,
                "start_char": chunk.metadata.start_char,
                "end_char": chunk.metadata.end_char,
            }

            if chunk.metadata.publication_date:
                payload["publication_date"] = chunk.metadata.publication_date.isoformat()
            if chunk.metadata.last_reviewed_date:
                payload["last_reviewed_date"] = chunk.metadata.last_reviewed_date.isoformat()

            points.append(
                qmodels.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload,
                )
            )

        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
        )
        logger.info(f"Upserted {len(points)} knowledge points into collection '{self.collection_name}'.")
        return len(points)

    def search_similarity(
        self,
        query_vector: List[float],
        top_k: int = 5,
        score_threshold: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """Searches Qdrant for top-k similar knowledge points matching query_vector.

        Returns ranked list of results containing reconstructed KnowledgeChunk and score.
        Does NOT mutate store or store query data.
        """
        if len(query_vector) != self.dimension:
            raise ValueError(
                f"Query vector dimension ({len(query_vector)}) does not match store dimension ({self.dimension})."
            )

        self.initialize()

        search_results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=top_k,
            score_threshold=score_threshold if score_threshold > 0.0 else None,
        )

        results: List[Dict[str, Any]] = []

        for hit in search_results:
            payload = hit.payload or {}
            score = float(hit.score)

            metadata = ChunkMetadata(
                source_type=SourceType(payload.get("source_type", SourceType.EDUCATIONAL_RESOURCE.value)),
                publisher=payload.get("publisher", "Unknown Publisher"),
                version=payload.get("version", "1.0"),
                reviewed=payload.get("reviewed", False),
                total_chunks=payload.get("total_chunks", 1),
                start_char=payload.get("start_char", 0),
                end_char=payload.get("end_char", len(payload.get("text", ""))),
            )

            chunk = KnowledgeChunk(
                chunk_id=payload.get("chunk_id", str(hit.id)),
                document_id=payload.get("document_id", "unknown_doc"),
                chunk_index=payload.get("chunk_index", 0),
                text=payload.get("text", ""),
                title=payload.get("title", "Untitled Document"),
                source_name=payload.get("source_name", "Unknown Source"),
                source_url=payload.get("source_url", "https://example.org/source"),
                topic=payload.get("topic", "general"),
                language=payload.get("language", "en"),
                metadata=metadata,
            )

            results.append({
                "chunk": chunk,
                "score": score,
                "payload": payload,
            })

        return results
