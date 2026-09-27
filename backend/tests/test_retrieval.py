from unittest.mock import MagicMock
import pytest
from app.knowledge.embeddings import DeterministicFakeEmbeddingService
from app.knowledge.retrieval import KnowledgeRetrievalService
from app.knowledge.schemas import ChunkMetadata, KnowledgeChunk, SourceType
from app.knowledge.vector_store import QdrantVectorStore


@pytest.fixture
def sample_retrieved_chunk():
    metadata = ChunkMetadata(
        source_type=SourceType.EDUCATIONAL_RESOURCE,
        publisher="Public Health Board",
        version="1.0",
        reviewed=True,
        total_chunks=1,
        start_char=0,
        end_char=60,
    )
    return KnowledgeChunk(
        chunk_id="doc-ret-01_c000",
        document_id="doc-ret-01",
        chunk_index=0,
        text="Deep breathing helps lower physiological stress and heart rate.",
        title="Deep Breathing Technique Guide",
        source_name="Health Education Institute",
        source_url="https://example.org/breathing-guide",
        topic="stress_management",
        language="en",
        metadata=metadata,
    )


@pytest.mark.asyncio
async def test_retrieval_query_embedding_and_provenance(sample_retrieved_chunk):
    """Test retrieval embeds query and returns ranked KnowledgeChunk results with preserved provenance."""
    fake_embedding = DeterministicFakeEmbeddingService(dimension=64)
    mock_vector_store = MagicMock(spec=QdrantVectorStore)

    mock_vector_store.search_similarity.return_value = [
        {
            "chunk": sample_retrieved_chunk,
            "score": 0.88,
            "payload": {"document_id": "doc-ret-01"},
        }
    ]

    retrieval_service = KnowledgeRetrievalService(
        vector_store=mock_vector_store,
        embedding_service=fake_embedding,
    )

    query = "How to reduce stress with breathing?"
    results = await retrieval_service.retrieve_relevant_chunks(query, top_k=3, score_threshold=0.7)

    assert len(results) == 1
    assert results[0]["score"] == 0.88
    retrieved = results[0]["chunk"]
    assert retrieved.title == "Deep Breathing Technique Guide"
    assert retrieved.source_name == "Health Education Institute"
    assert str(retrieved.source_url).rstrip("/") == "https://example.org/breathing-guide"
    assert retrieved.topic == "stress_management"

    mock_vector_store.search_similarity.assert_called_once()
    mock_vector_store.upsert_chunks.assert_not_called()  # Search does NOT mutate store


@pytest.mark.asyncio
async def test_retrieval_empty_query_rejection():
    """Test empty or whitespace query input raises ValueError."""
    fake_embedding = DeterministicFakeEmbeddingService()
    mock_vector_store = MagicMock(spec=QdrantVectorStore)
    retrieval_service = KnowledgeRetrievalService(
        vector_store=mock_vector_store,
        embedding_service=fake_embedding,
    )

    with pytest.raises(ValueError):
        await retrieval_service.retrieve_relevant_chunks("")

    with pytest.raises(ValueError):
        await retrieval_service.retrieve_relevant_chunks("   \t\n ")
