from typing import Any, Dict, List, Optional
from app.config import settings
from app.knowledge.embeddings import BaseEmbeddingService, get_embedding_service
from app.knowledge.schemas import KnowledgeChunk
from app.knowledge.vector_store import QdrantVectorStore
from app.knowledge.operation_executor import run_knowledge_operation
from app.knowledge.secure_approval_loader import load_secure_approval_registry


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
        self.embedding_service = embedding_service
        self.vector_store = vector_store

    def _get_vector_store(self):
        if self.vector_store is None:
            self.vector_store = QdrantVectorStore()
        return self.vector_store

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

        registry = load_secure_approval_registry()

        # Step 1: Embed query text
        if self.embedding_service is None:
            self.embedding_service = get_embedding_service()

        query_vector = await self.embedding_service.embed_text(clean_query)

        # Step 2: Search Qdrant vector store
        def search():
            return self._get_vector_store().search_similarity(
                query_vector=query_vector,
                top_k=top_k,
                score_threshold=score_threshold,
            )

        results = await run_knowledge_operation(search)

        return [
            result for result in results
            if isinstance(result.get("chunk"), KnowledgeChunk)
            and result["chunk"].metadata.reviewed is True
            and registry.is_chunk_approved(result["chunk"])
        ]
