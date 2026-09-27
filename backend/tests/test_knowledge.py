import pytest
from pydantic import ValidationError
from app.knowledge import (
    KnowledgeChunk,
    KnowledgeDocument,
    SourceMetadata,
    SourceRegistry,
    SourceType,
    chunk_document,
    validate_knowledge_document,
)


def test_valid_knowledge_document_creation():
    """Test creating a valid KnowledgeDocument instance."""
    doc = KnowledgeDocument(
        document_id="doc-001",
        title="Understanding Daily Stress Management",
        source_name="National Institute of Mental Health",
        source_url="https://example.org/stress-management",
        source_type=SourceType.EDUCATIONAL_RESOURCE,
        publisher="Public Health Organization",
        topic="stress_management",
        content="Stress is a natural physical and mental reaction to life experiences. Deep breathing and mindfulness can help reduce stress levels.",
        version="1.0",
        reviewed=True,
    )
    assert doc.document_id == "doc-001"
    assert doc.title == "Understanding Daily Stress Management"
    assert str(doc.source_url).rstrip("/") == "https://example.org/stress-management"
    assert doc.source_type == SourceType.EDUCATIONAL_RESOURCE
    assert doc.reviewed is True
    assert validate_knowledge_document(doc) is True


def test_invalid_source_url():
    """Test invalid source URL raises Pydantic ValidationError."""
    with pytest.raises(ValidationError):
        KnowledgeDocument(
            document_id="doc-002",
            title="Invalid URL Test",
            source_name="Test Source",
            source_url="not-a-valid-url",
            source_type=SourceType.EDUCATIONAL_RESOURCE,
            publisher="Test Publisher",
            topic="testing",
            content="Valid text content here.",
        )


def test_missing_required_fields():
    """Test missing required fields raise Pydantic ValidationError."""
    with pytest.raises(ValidationError):
        KnowledgeDocument(
            document_id="doc-003",
            title="Missing Topic",
            source_name="Test Source",
            source_url="https://example.org/source",
            source_type=SourceType.EDUCATIONAL_RESOURCE,
            publisher="Test Publisher",
            # topic omitted
            content="Valid text content here.",
        )


def test_empty_content_rejection():
    """Test empty or whitespace content raises ValueError."""
    with pytest.raises(ValueError):
        KnowledgeDocument(
            document_id="doc-004",
            title="Empty Content Test",
            source_name="Test Source",
            source_url="https://example.org/source",
            source_type=SourceType.EDUCATIONAL_RESOURCE,
            publisher="Test Publisher",
            topic="testing",
            content="   ",
        )


def test_deterministic_chunk_ids_and_ordering():
    """Test chunking produces deterministic chunk IDs and ordering."""
    sample_text = (
        "Cognitive reframing is a psychological technique that helps individuals identify "
        "and change negative or unhelpful thought patterns. By practicing cognitive reframing, "
        "people can learn to view challenging situations in a more balanced and realistic light."
    )
    doc = KnowledgeDocument(
        document_id="doc-stress-101",
        title="Cognitive Reframing Overview",
        source_name="Psychology Educational Board",
        source_url="https://example.org/reframing",
        source_type=SourceType.EDUCATIONAL_RESOURCE,
        publisher="Educational Board",
        topic="cognitive_reframing",
        content=sample_text,
    )

    chunks_run1 = chunk_document(doc, max_chunk_size=100, overlap=20)
    chunks_run2 = chunk_document(doc, max_chunk_size=100, overlap=20)

    assert len(chunks_run1) > 1
    assert len(chunks_run1) == len(chunks_run2)

    for i in range(len(chunks_run1)):
        assert chunks_run1[i].chunk_id == f"doc-stress-101_c{i:03d}"
        assert chunks_run1[i].chunk_id == chunks_run2[i].chunk_id
        assert chunks_run1[i].chunk_index == i
        assert chunks_run1[i].text == chunks_run2[i].text


def test_chunk_metadata_preservation():
    """Test chunks inherit and preserve document metadata."""
    doc = KnowledgeDocument(
        document_id="doc-meta-01",
        title="Metadata Inheritance Test",
        source_name="Health Board",
        source_url="https://example.org/health",
        source_type=SourceType.PUBLIC_HEALTH_INFORMATION,
        publisher="Health Org",
        topic="general_wellness",
        content="Sample content for checking metadata preservation.",
        version="2.0",
        reviewed=True,
    )

    chunks = chunk_document(doc, max_chunk_size=30, overlap=5)
    for chunk in chunks:
        assert chunk.document_id == "doc-meta-01"
        assert chunk.title == "Metadata Inheritance Test"
        assert chunk.source_name == "Health Board"
        assert str(chunk.source_url).rstrip("/") == "https://example.org/health"
        assert chunk.topic == "general_wellness"
        assert chunk.metadata.publisher == "Health Org"
        assert chunk.metadata.version == "2.0"
        assert chunk.metadata.reviewed is True
        assert chunk.metadata.total_chunks == len(chunks)


def test_chunk_overlap_behavior():
    """Test sliding window overlap behavior across sequential chunks."""
    content = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    doc = KnowledgeDocument(
        document_id="doc-overlap-01",
        title="Overlap Test",
        source_name="Test Source",
        source_url="https://example.org/overlap",
        source_type=SourceType.EDUCATIONAL_RESOURCE,
        publisher="Publisher",
        topic="testing",
        content=content,
    )

    chunks = chunk_document(doc, max_chunk_size=10, overlap=3)
    # Chunk 0: chars 0..10 ("0123456789"), next start = 10-3 = 7
    # Chunk 1: chars 7..17 ("789ABCDEFG")
    assert chunks[0].text == "0123456789"
    assert chunks[1].text == "789ABCDEFG"
    assert chunks[0].text[-3:] == chunks[1].text[:3]


def test_source_registry_operations():
    """Test SourceRegistry add, retrieve, list, and clear methods."""
    registry = SourceRegistry()
    registry.clear()
    assert len(registry.list_sources()) == 0

    source = SourceMetadata(
        source_name="CDC Mental Health Guidelines",
        publisher="Centers for Disease Control and Prevention",
        source_url="https://example.org/cdc-guidelines",
        source_type=SourceType.GUIDELINE,
        topic="mental_health_guidelines",
        review_status="APPROVED",
    )

    registered = registry.register_source(source)
    assert registered.source_name == "CDC Mental Health Guidelines"
    assert len(registry.list_sources()) == 1

    retrieved = registry.get_source("CDC Mental Health Guidelines")
    assert retrieved is not None
    assert retrieved.publisher == "Centers for Disease Control and Prevention"
    assert retrieved.review_status == "APPROVED"


def test_no_user_specific_fields_in_schemas():
    """Verify KnowledgeDocument and KnowledgeChunk schemas contain no user-specific fields."""
    doc_fields = KnowledgeDocument.model_fields.keys()
    chunk_fields = KnowledgeChunk.model_fields.keys()

    prohibited_terms = {"user_id", "user", "conversation_id", "diagnosis", "patient", "medical_record"}

    for term in prohibited_terms:
        assert term not in doc_fields
        assert term not in chunk_fields
