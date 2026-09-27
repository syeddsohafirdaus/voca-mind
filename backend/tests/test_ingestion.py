from unittest.mock import MagicMock
import pytest
from app.knowledge.embeddings import DeterministicFakeEmbeddingService
from app.knowledge.ingestion import KnowledgeIngestionPipeline
from app.knowledge.schemas import KnowledgeDocument, SourceType
from app.knowledge.vector_store import QdrantVectorStore


@pytest.fixture
def sample_document():
    return KnowledgeDocument(
        document_id="doc-ingest-01",
        title="Mindfulness Practice Guide",
        source_name="National Health Foundation",
        source_url="https://example.org/mindfulness",
        source_type=SourceType.EDUCATIONAL_RESOURCE,
        publisher="Health Foundation",
        topic="mindfulness",
        content="Mindfulness is the psychological process of bringing one's attention to experiences occurring in the present moment.",
        version="1.0",
        reviewed=True,
    )


@pytest.mark.asyncio
async def test_full_ingestion_pipeline_success(sample_document):
    """Test full ingestion pipeline validates, chunks, embeds, and upserts knowledge document."""
    fake_embedding = DeterministicFakeEmbeddingService(dimension=64)
    mock_vector_store = MagicMock(spec=QdrantVectorStore)
    mock_vector_store.upsert_chunks.return_value = 1

    pipeline = KnowledgeIngestionPipeline(
        vector_store=mock_vector_store,
        embedding_service=fake_embedding,
    )

    result = await pipeline.ingest_document(sample_document, max_chunk_size=200, overlap=20)

    assert result["status"] == "SUCCESS"
    assert result["document_id"] == "doc-ingest-01"
    assert result["chunks_ingested"] == 1

    mock_vector_store.upsert_chunks.assert_called_once()
    chunks, vectors = mock_vector_store.upsert_chunks.call_args.args
    assert len(chunks) == 1
    assert len(vectors) == 1
    assert len(vectors[0]) == 64
    assert chunks[0].chunk_id == "doc-ingest-01_c000"

    # Verify no user fields in vector payload
    payload = mock_vector_store.upsert_chunks.call_args.args[0][0].model_dump()
    for forbidden in ["user_id", "user", "conversation_id", "patient", "diagnosis"]:
        assert forbidden not in payload


@pytest.mark.asyncio
async def test_ingestion_pipeline_invalid_document_rejection():
    """Test ingestion pipeline rejects invalid documents with blank content."""
    fake_embedding = DeterministicFakeEmbeddingService()
    mock_vector_store = MagicMock(spec=QdrantVectorStore)
    pipeline = KnowledgeIngestionPipeline(
        vector_store=mock_vector_store,
        embedding_service=fake_embedding,
    )

    with pytest.raises(ValueError):
        invalid_doc = KnowledgeDocument(
            document_id="doc-bad-01",
            title="Bad Document",
            source_name="Source",
            source_url="https://example.org/bad",
            source_type=SourceType.EDUCATIONAL_RESOURCE,
            publisher="Publisher",
            topic="testing",
            content="   ",  # Blank content
        )
        await pipeline.ingest_document(invalid_doc)
