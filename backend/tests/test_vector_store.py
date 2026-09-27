from unittest.mock import MagicMock
import pytest
from qdrant_client.http import models as qmodels

from app.knowledge.schemas import ChunkMetadata, KnowledgeChunk, SourceType
from app.knowledge.vector_store import QdrantVectorStore


@pytest.fixture
def mock_qdrant_client():
    """Mock Qdrant client for offline unit testing."""
    client = MagicMock()
    client.collection_exists.return_value = True
    client.get_collections.return_value = MagicMock(collections=[MagicMock(name="voca_mind_knowledge")])
    return client


def create_sample_chunk(chunk_id: str = "doc-01_c000") -> KnowledgeChunk:
    metadata = ChunkMetadata(
        source_type=SourceType.EDUCATIONAL_RESOURCE,
        publisher="Health Agency",
        version="1.0",
        reviewed=True,
        total_chunks=1,
        start_char=0,
        end_char=50,
    )
    return KnowledgeChunk(
        chunk_id=chunk_id,
        document_id="doc-01",
        chunk_index=0,
        text="Sample text content for vector store testing.",
        title="Sample Document Title",
        source_name="Sample Source Agency",
        source_url="https://example.org/sample-source",
        topic="stress_management",
        language="en",
        metadata=metadata,
    )


def test_idempotent_collection_initialization(mock_qdrant_client):
    """Test initializing vector store is idempotent and does not recreate existing collection."""
    store = QdrantVectorStore(client=mock_qdrant_client, dimension=128)
    assert store.initialize() is True
    mock_qdrant_client.collection_exists.assert_called_once_with(store.collection_name)
    mock_qdrant_client.create_collection.assert_not_called()


def test_upsert_chunks_provenance_preservation(mock_qdrant_client):
    """Test upserting chunks constructs PointStruct items preserving full source provenance payload."""
    store = QdrantVectorStore(client=mock_qdrant_client, dimension=128)
    chunk = create_sample_chunk("doc-01_c000")
    dummy_vector = [0.1] * 128

    upserted_count = store.upsert_chunks([chunk], [dummy_vector])
    assert upserted_count == 1
    mock_qdrant_client.upsert.assert_called_once()

    call_kwargs = mock_qdrant_client.upsert.call_args.kwargs
    assert call_kwargs["collection_name"] == store.collection_name
    points = call_kwargs["points"]
    assert len(points) == 1

    point = points[0]
    assert point.vector == dummy_vector
    payload = point.payload
    assert payload["document_id"] == "doc-01"
    assert payload["chunk_id"] == "doc-01_c000"
    assert payload["title"] == "Sample Document Title"
    assert payload["source_name"] == "Sample Source Agency"
    assert payload["source_url"] == "https://example.org/sample-source"
    assert payload["topic"] == "stress_management"
    assert payload["publisher"] == "Health Agency"


def test_dimension_mismatch_rejection(mock_qdrant_client):
    """Test upserting vectors with mismatched dimension raises ValueError."""
    store = QdrantVectorStore(client=mock_qdrant_client, dimension=128)
    chunk = create_sample_chunk("doc-01_c000")
    invalid_vector = [0.1] * 64  # Store expects 128

    with pytest.raises(ValueError):
        store.upsert_chunks([chunk], [invalid_vector])


def test_similarity_search(mock_qdrant_client):
    """Test similarity search executes client.search and formats ranked results."""
    chunk = create_sample_chunk("doc-01_c000")
    payload = {
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
        "total_chunks": 1,
        "start_char": 0,
        "end_char": 50,
    }

    mock_hit = MagicMock()
    mock_hit.id = "point-id-1"
    mock_hit.score = 0.92
    mock_hit.payload = payload

    mock_qdrant_client.search.return_value = [mock_hit]

    store = QdrantVectorStore(client=mock_qdrant_client, dimension=128)
    query_vec = [0.1] * 128

    results = store.search_similarity(query_vec, top_k=3, score_threshold=0.7)
    assert len(results) == 1
    assert results[0]["score"] == 0.92
    assert results[0]["chunk"].title == "Sample Document Title"
    assert results[0]["chunk"].source_name == "Sample Source Agency"
