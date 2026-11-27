from typing import Any, Dict, Optional
from app.knowledge.embeddings import BaseEmbeddingService, get_embedding_service
from app.knowledge.schemas import KnowledgeDocument
from app.knowledge.service import chunk_document, validate_knowledge_document
from app.knowledge.vector_store import QdrantVectorStore
from app.knowledge.operation_executor import run_knowledge_operation
from app.knowledge.secure_approval_loader import load_secure_approval_registry
from app.logger import logger


class KnowledgeIngestionPipeline:
    """Pipeline for validating, chunking, embedding, and indexing reviewed KnowledgeDocuments into Qdrant.

    Safety & Provenance Guarantees:
    - Validates document completeness before processing.
    - Uses deterministic chunk IDs and ordering.
    - Preserves source provenance metadata in all vectors.
    - Does NOT store user data or execute destructive collection replacements.
    """

    def __init__(
        self,
        vector_store: Optional[QdrantVectorStore] = None,
        embedding_service: Optional[BaseEmbeddingService] = None,
    ) -> None:
        self.embedding_service = (
            embedding_service if embedding_service is not None else get_embedding_service()
        )
        self.vector_store = vector_store

    def _get_vector_store(self):
        if self.vector_store is None:
            self.vector_store = QdrantVectorStore()
        return self.vector_store

    async def ingest_document(
        self,
        doc: KnowledgeDocument,
        max_chunk_size: int = 500,
        overlap: int = 50,
    ) -> Dict[str, Any]:
        """Asynchronously validates, chunks, embeds, and indexes a KnowledgeDocument.

        Returns ingestion summary dictionary.
        Raises ValueError if validation fails or parameters are invalid.
        """
        # Step 1: Validate document
        validate_knowledge_document(doc)

        if doc.reviewed is not True:
            raise ValueError(
                "Unreviewed knowledge documents cannot be ingested."
            )

        registry = load_secure_approval_registry()

        if not registry.is_approved(doc):
            raise ValueError(
                "Document lacks valid signed approval."
            )

        # Step 2: Chunk document deterministically
        chunks = chunk_document(doc, max_chunk_size=max_chunk_size, overlap=overlap)
        if not chunks:
            raise ValueError(f"No chunks generated for document '{doc.document_id}'.")

        if not all(
            registry.is_chunk_approved(chunk)
            for chunk in chunks
        ):
            raise ValueError(
                "Document chunks lack signed approval."
            )

        # Step 3: Embed chunk texts
        texts = [chunk.text for chunk in chunks]
        vectors = await self.embedding_service.embed_batch(texts)

        # Step 4: Upsert into Qdrant vector store
        def upsert():
            return self._get_vector_store().upsert_chunks(chunks, vectors)

        upserted_count = await run_knowledge_operation(upsert)

        logger.info(
            f"Successfully ingested KnowledgeDocument id='{doc.document_id}' "
            f"chunks={upserted_count} into Qdrant collection."
        )

        return {
            "document_id": doc.document_id,
            "title": doc.title,
            "source_name": doc.source_name,
            "chunks_ingested": upserted_count,
            "status": "SUCCESS",
        }
