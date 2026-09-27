from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class SourceType(str, Enum):
    """Source type categorization for knowledge base documents."""

    GUIDELINE = "guideline"
    PUBLIC_HEALTH_INFORMATION = "public_health_information"
    EDUCATIONAL_RESOURCE = "educational_resource"
    CRISIS_RESOURCE = "crisis_resource"
    RESEARCH_SUMMARY = "research_summary"


class KnowledgeDocument(BaseModel):
    """Represents a curated, non-diagnostic knowledge base document.

    MUST NOT contain user IDs, conversation IDs, or individualized user statements.
    """

    document_id: str = Field(
        ...,
        min_length=1,
        description="Unique, stable identifier for the document."
    )
    title: str = Field(
        ...,
        min_length=1,
        description="Document title."
    )
    source_name: str = Field(
        ...,
        min_length=1,
        description="Authoritative source name."
    )
    source_url: HttpUrl = Field(
        ...,
        description="Validated URL of origin for provenance."
    )
    source_type: SourceType = Field(
        ...,
        description="Type category of knowledge source."
    )
    publisher: str = Field(
        ...,
        min_length=1,
        description="Publishing entity."
    )
    publication_date: Optional[datetime] = Field(
        default=None,
        description="Original publication date."
    )
    last_reviewed_date: Optional[datetime] = Field(
        default=None,
        description="Date content was last reviewed."
    )
    language: str = Field(
        default="en",
        description="Language code (default 'en')."
    )
    topic: str = Field(
        ...,
        min_length=1,
        description="Primary psychoeducational topic."
    )
    content: str = Field(
        ...,
        min_length=1,
        description="Educational text content."
    )
    version: str = Field(
        default="1.0",
        description="Document schema version."
    )
    reviewed: bool = Field(
        default=False,
        description="Review verification status."
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Record creation timestamp."
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Record last update timestamp."
    )

    @field_validator("content", "title", "source_name", "publisher", "topic", "document_id")
    @classmethod
    def validate_non_blank_string(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Field cannot be empty or whitespace.")
        return stripped

    model_config = ConfigDict(frozen=True)


class ChunkMetadata(BaseModel):
    """Structured metadata preserved within every knowledge chunk."""

    source_type: SourceType
    publisher: str
    version: str
    reviewed: bool
    publication_date: Optional[datetime] = None
    last_reviewed_date: Optional[datetime] = None
    total_chunks: int = Field(
        ...,
        ge=1,
        description="Total chunks generated from parent document."
    )
    start_char: int = Field(
        ...,
        ge=0,
        description="Start character index in parent document."
    )
    end_char: int = Field(
        ...,
        ge=0,
        description="End character index in parent document."
    )

    model_config = ConfigDict(frozen=True)


class KnowledgeChunk(BaseModel):
    """Represents a chunk derived from a KnowledgeDocument for vector indexing."""

    chunk_id: str = Field(
        ...,
        description="Deterministic, unique chunk identifier."
    )
    document_id: str = Field(
        ...,
        description="Reference ID of parent KnowledgeDocument."
    )
    chunk_index: int = Field(
        ...,
        ge=0,
        description="Zero-based index of chunk in sequence."
    )
    text: str = Field(
        ...,
        min_length=1,
        description="Chunk text content."
    )
    title: str = Field(
        ...,
        description="Inherited document title."
    )
    source_name: str = Field(
        ...,
        description="Inherited source name."
    )
    source_url: HttpUrl = Field(
        ...,
        description="Inherited source URL."
    )
    topic: str = Field(
        ...,
        description="Inherited topic category."
    )
    language: str = Field(
        default="en",
        description="Language code."
    )
    metadata: ChunkMetadata = Field(
        ...,
        description="Structured chunk metadata preserving source provenance."
    )

    model_config = ConfigDict(frozen=True)
