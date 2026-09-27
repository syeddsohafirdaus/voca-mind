from typing import Any, Dict, List, Optional
from app.config import settings
from app.knowledge.embeddings import BaseEmbeddingService, get_embedding_service
from app.knowledge.schemas import KnowledgeChunk
from app.knowledge.vector_store import QdrantVectorStore


class KnowledgeRetrievalService:
    """Service responsible for semantic query embedding and vector similarity retrieval from Qdrant.

    Responsibilities:
    - Embeds search queries.
    - Performs vector similarity search against curated Qdrant knowledge collections.
    - Preserves source provenance in all returned chunks.
    - Does NOT modify vector store or generate LLM responses.
    - Does NOT process user identity or medical diagnoses.
    """

    def __init__(
        self,
        vector_store: Optional[QdrantVectorStore] = None,
        embedding_service: Optional[BaseEmbeddingService] = None,
    ) -> None:
        self.embedding_service = (
            embedding_service if embedding_service is not None else get_embedding_service()
        )
        self.vector_store = (
            vector_store if vector_store is not None else QdrantVectorStore()
        )

    async def retrieve_relevant_chunks(
        self,
        query: str,
        top_k: int = 5,
        score_threshold: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """Asynchronously embeds query and retrieves top-k relevant KnowledgeChunks from Qdrant.

        Parameters:
        - query: Non-empty search query string.
        - top_k: Maximum number of ranked results to return.
        - score_threshold: Minimum similarity score threshold (0.0 to 1.0).

        Returns list of result dictionaries containing 'chunk', 'score', and 'payload'.
        Raises ValueError if query is empty or parameters are invalid.
        """
        if not query or not query.strip():
            raise ValueError("Query text cannot be empty or blank.")
        if top_k <= 0:
            raise ValueError("top_k must be greater than 0.")

        clean_query = query.strip()

        # Step 1: Embed query text
        query_vector = await self.embedding_service.embed_text(clean_query)

        # Step 2: Search Qdrant vector store
        results = self.vector_store.search_similarity(
            query_vector=query_vector,
            top_k=top_k,
            score_threshold=score_threshold,
        )

        return results
