from datetime import datetime, timezone

import pytest

from app.knowledge.approval import (
    DocumentApproval,
    ApprovalRegistry,
    document_fingerprint,
)
from app.knowledge.schemas import (
    KnowledgeDocument,
    SourceType,
)


@pytest.fixture
def document():
    return KnowledgeDocument(
        document_id="synthetic-doc-001",
        title="Synthetic Approval Test",
        source_name="Test Source",
        source_url="https://example.org/test",
        source_type=SourceType.EDUCATIONAL_RESOURCE,
        publisher="Test Publisher",
        topic="testing",
        content="Synthetic content for testing only.",
        version="1.0",
        reviewed=True,
    )


@pytest.fixture
def registry(document):
    registry = ApprovalRegistry()

    registry.register(
        DocumentApproval(
            document_id=document.document_id,
            version=document.version,
            fingerprint=document_fingerprint(document),
            reviewer_id="synthetic-test-reviewer",
            approved_at=datetime.now(timezone.utc),
        )
    )

    return registry


def test_fingerprint_consistency(document):
    assert document_fingerprint(document) == \
        document_fingerprint(document)

    assert len(document_fingerprint(document)) == 64


def test_approved_document(document, registry):
    assert registry.is_approved(document)


def test_unregistered_document(document):
    registry = ApprovalRegistry()
    assert not registry.is_approved(document)


def test_modified_content(document, registry):
    modified = document.model_copy(
        update={"content": "Modified content."}
    )

    assert not registry.is_approved(modified)


def test_modified_source(document, registry):
    modified = document.model_copy(
        update={"publisher": "Different Publisher"}
    )

    assert not registry.is_approved(modified)


def test_modified_version(document, registry):
    modified = document.model_copy(
        update={"version": "2.0"}
    )

    assert not registry.is_approved(modified)


def test_unreviewed_document(document, registry):
    modified = document.model_copy(
        update={"reviewed": False}
    )

    assert not registry.is_approved(modified)


def test_revoked_document(document, registry):
    registry.revoke(
        document.document_id,
        document.version,
    )

    assert not registry.is_approved(document)


def test_unknown_revocation():
    registry = ApprovalRegistry()

    with pytest.raises(ValueError):
        registry.revoke("unknown", "1.0")
