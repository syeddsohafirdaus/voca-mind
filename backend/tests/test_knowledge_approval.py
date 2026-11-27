from unittest.mock import MagicMock, AsyncMock

import pytest

from app.knowledge.ingestion import KnowledgeIngestionPipeline
from app.knowledge.retrieval import KnowledgeRetrievalService
from app.knowledge.schemas import KnowledgeDocument, SourceType
from app.knowledge.service import chunk_document
from app.knowledge.vector_store import QdrantVectorStore


def make_document(reviewed=False):
    return KnowledgeDocument(
        document_id="synthetic-approval-test",
        title="Synthetic Test Document",
        source_name="Test Source",
        source_url="https://example.org/test",
        source_type=SourceType.EDUCATIONAL_RESOURCE,
        publisher="Test Publisher",
        topic="testing",
        content="Synthetic content for automated testing only.",
        reviewed=reviewed,
    )


@pytest.mark.asyncio
async def test_unreviewed_document_rejected():
    embedding = AsyncMock()
    store = MagicMock()

    pipeline = KnowledgeIngestionPipeline(
        vector_store=store,
        embedding_service=embedding,
    )

    with pytest.raises(ValueError, match="Unreviewed"):
        await pipeline.ingest_document(
            make_document(False)
        )

    embedding.embed_batch.assert_not_called()
    store.upsert_chunks.assert_not_called()


def test_unreviewed_vector_rejected():
    client = MagicMock()

    store = QdrantVectorStore(
        client=client,
        dimension=64,
    )

    chunks = chunk_document(make_document(False))
    vectors = [[0.1] * 64 for _ in chunks]

    with pytest.raises(ValueError, match="Unreviewed"):
        store.upsert_chunks(chunks, vectors)

    client.upsert.assert_not_called()


@pytest.mark.asyncio
async def test_retrieval_excludes_unreviewed_chunks(signed_test_approval):
    embedding = AsyncMock()
    embedding.embed_text.return_value = [0.1] * 64

    store = MagicMock()

    approved_doc = make_document(True)
    reviewed = chunk_document(approved_doc)[0]

    signed_test_approval(
        approved_doc,
        [reviewed],
    )
    unreviewed = chunk_document(make_document(False))[0]

    store.search_similarity.return_value = [
        {"chunk": unreviewed, "score": 0.99},
        {"chunk": reviewed, "score": 0.85},
    ]

    service = KnowledgeRetrievalService(
        vector_store=store,
        embedding_service=embedding,
    )

    results = await service.retrieve_relevant_chunks(
        "Synthetic test query"
    )

    assert len(results) == 1
    assert results[0]["chunk"].metadata.reviewed is True


def test_vector_search_excludes_unreviewed_payload():
    client = MagicMock()

    store = QdrantVectorStore(
        client=client,
        dimension=64,
    )

    store.initialize = MagicMock(return_value=True)

    hit = MagicMock()
    hit.payload = {"reviewed": False}
    hit.score = 0.99

    client.query_points.return_value.points = [hit]

    results = store.search_similarity([0.1] * 64)

    assert results == []

    query_filter = client.query_points.call_args.kwargs[
        "query_filter"
    ]

    assert query_filter.must[0].key == "reviewed"
    assert query_filter.must[0].match.value is True


@pytest.mark.asyncio
async def test_signed_approval_rejects_modified_document(
    signed_test_approval,
):
    doc = make_document(True)

    signed_test_approval(
        doc,
        chunk_document(doc),
    )

    modified = doc.model_copy(
        update={"content": "Modified synthetic content."}
    )

    embedding = AsyncMock()
    store = MagicMock()

    pipeline = KnowledgeIngestionPipeline(
        vector_store=store,
        embedding_service=embedding,
    )

    with pytest.raises(ValueError, match="signed approval"):
        await pipeline.ingest_document(modified)

    embedding.embed_batch.assert_not_called()
    store.upsert_chunks.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "scenario",
    ["approved", "tampered", "revoked", "unknown"],
)
async def test_signed_chunk_retrieval(
    signed_test_approval,
    scenario,
):
    doc = make_document(True)
    chunk = chunk_document(doc)[0]

    signed_test_approval(
        doc,
        [chunk],
        status=(
            "REVOKED"
            if scenario == "revoked"
            else "APPROVED"
        ),
    )

    candidate = chunk

    if scenario == "tampered":
        candidate = chunk.model_copy(
            update={"text": "Tampered synthetic content."}
        )

    elif scenario == "unknown":
        candidate = chunk.model_copy(
            update={"document_id": "unknown-document"}
        )

    embedding = AsyncMock()
    embedding.embed_text.return_value = [0.1] * 64

    store = MagicMock()
    store.search_similarity.return_value = [
        {"chunk": candidate, "score": 0.95}
    ]

    service = KnowledgeRetrievalService(
        vector_store=store,
        embedding_service=embedding,
    )

    results = await service.retrieve_relevant_chunks(
        "Synthetic query"
    )

    if scenario == "approved":
        assert len(results) == 1
        assert results[0]["chunk"] == chunk
    else:
        assert results == []
