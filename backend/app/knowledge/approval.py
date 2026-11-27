"""Document-level knowledge approval verification."""

import hashlib
import json
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.knowledge.schemas import KnowledgeDocument, KnowledgeChunk


def document_fingerprint(doc: KnowledgeDocument) -> str:
    """Generate a fingerprint of content and provenance."""

    payload = doc.model_dump(
        mode="json",
        exclude={
            "created_at",
            "updated_at",
            "reviewed",
            "last_reviewed_date",
        },
    )

    canonical = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()


def chunk_fingerprint(chunk: KnowledgeChunk) -> str:
    """Fingerprint chunk content and provenance."""

    canonical = json.dumps(
        chunk.model_dump(mode="json"),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        canonical.encode("utf-8")
    ).hexdigest()


class DocumentApproval(BaseModel):
    document_id: str = Field(min_length=1)
    version: str = Field(min_length=1)

    fingerprint: str = Field(
        pattern=r"^[a-f0-9]{64}$"
    )

    chunk_fingerprints: tuple[str, ...] = Field(
        default_factory=tuple
    )

    reviewer_id: str = Field(min_length=1)
    approved_at: datetime

    status: Literal[
        "APPROVED", "REVOKED"
    ] = "APPROVED"

    model_config = ConfigDict(frozen=True)


class ApprovalRegistry:
    """Registry of trusted document approval records."""

    def __init__(self):
        self._records = {}

    def register(self, approval: DocumentApproval):
        key = (
            approval.document_id,
            approval.version,
        )
        self._records[key] = approval

    def get(self, document_id, version):
        return self._records.get(
            (document_id, version)
        )

    def is_approved(self, doc: KnowledgeDocument) -> bool:
        if not doc.reviewed:
            return False

        approval = self.get(
            doc.document_id,
            doc.version,
        )

        if approval is None:
            return False

        if approval.status != "APPROVED":
            return False

        return (
            approval.fingerprint
            == document_fingerprint(doc)
        )

    def is_chunk_approved(
        self,
        chunk: KnowledgeChunk,
    ) -> bool:

        if chunk.metadata.reviewed is not True:
            return False

        approval = self.get(
            chunk.document_id,
            chunk.metadata.version,
        )

        if approval is None:
            return False

        if approval.status != "APPROVED":
            return False

        return (
            chunk_fingerprint(chunk)
            in approval.chunk_fingerprints
        )

    def revoke(self, document_id, version):
        key = (document_id, version)

        if key not in self._records:
            raise ValueError("Approval record not found.")

        self._records[key] = self._records[key].model_copy(
            update={"status": "REVOKED"}
        )
