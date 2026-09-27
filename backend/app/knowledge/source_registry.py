from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, HttpUrl
from app.knowledge.schemas import SourceType


class SourceMetadata(BaseModel):
    """Metadata record for an authoritative knowledge source in the registry."""

    source_name: str = Field(..., min_length=1, description="Unique source name.")
    publisher: str = Field(..., min_length=1, description="Publishing organization.")
    source_url: HttpUrl = Field(..., description="Canonical source URL.")
    source_type: SourceType = Field(..., description="Type of knowledge source.")
    language: str = Field(default="en", description="Language code.")
    topic: str = Field(..., min_length=1, description="Primary topic domain.")
    review_status: str = Field(
        default="UNREVIEWED",
        description="Review approval status (e.g. 'UNREVIEWED', 'APPROVED', 'DEPRECATED')."
    )

    model_config = ConfigDict(frozen=True)


class SourceRegistry:
    """In-memory source registry abstraction for tracking authoritative knowledge sources.

    Production Note:
    Production ingestion MUST only register sources that have undergone formal review and approval.
    No fabricated or unverified sources should be added.
    """

    def __init__(self) -> None:
        self._sources: Dict[str, SourceMetadata] = {}

    def register_source(self, source: SourceMetadata) -> SourceMetadata:
        """Registers a new source metadata record. Overwrites if source_name exists."""
        self._sources[source.source_name] = source
        return source

    def get_source(self, source_name: str) -> Optional[SourceMetadata]:
        """Retrieves registered source metadata by source_name."""
        return self._sources.get(source_name)

    def list_sources(self) -> List[SourceMetadata]:
        """Lists all registered sources."""
        return list(self._sources.values())

    def clear(self) -> None:
        """Clears all in-memory sources (primarily for testing)."""
        self._sources.clear()
