import pytest
from app.config import settings
from app.knowledge.embeddings import DeterministicFakeEmbeddingService


@pytest.mark.asyncio
async def test_deterministic_fake_embeddings_same_input():
    """Test deterministic fake embedding service produces identical vectors for identical inputs."""
    service = DeterministicFakeEmbeddingService(dimension=settings.EMBEDDING_DIMENSION)
    text = "Mindfulness and stress reduction techniques."

    vec1 = await service.embed_text(text)
    vec2 = await service.embed_text(text)

    assert len(vec1) == settings.EMBEDDING_DIMENSION
    assert len(vec2) == settings.EMBEDDING_DIMENSION
    assert vec1 == vec2


@pytest.mark.asyncio
async def test_deterministic_fake_embeddings_distinct_inputs():
    """Test distinct input texts produce distinct vectors."""
    service = DeterministicFakeEmbeddingService(dimension=128)
    text1 = "Deep breathing exercises"
    text2 = "Sleep hygiene principles"

    vec1 = await service.embed_text(text1)
    vec2 = await service.embed_text(text2)

    assert len(vec1) == 128
    assert len(vec2) == 128
    assert vec1 != vec2


@pytest.mark.asyncio
async def test_batch_embedding_behavior():
    """Test batch embedding returns matching number of vectors in correct order."""
    service = DeterministicFakeEmbeddingService(dimension=64)
    texts = ["First paragraph text", "Second paragraph text", "Third paragraph text"]

    vectors = await service.embed_batch(texts)
    assert len(vectors) == 3
    for v in vectors:
        assert len(v) == 64

    # Verify order matches single embedding calls
    v0_single = await service.embed_text(texts[0])
    assert vectors[0] == v0_single


@pytest.mark.asyncio
async def test_empty_or_whitespace_input_rejection():
    """Test empty string or whitespace text input raises ValueError."""
    service = DeterministicFakeEmbeddingService()

    with pytest.raises(ValueError):
        await service.embed_text("")

    with pytest.raises(ValueError):
        await service.embed_text("   \n\t  ")

    with pytest.raises(ValueError):
        await service.embed_batch(["Valid text", ""])
