#!/usr/bin/env python3
"""Example script demonstrating ingestion of a reviewed KnowledgeDocument into Qdrant.

Usage:
    python scripts/ingest_example_document.py

Safety & Production Boundary:
- Uses placeholder example document only.
- Fails explicitly if production environment is configured without real Qdrant credentials.
- Does NOT contain real API keys or sensitive patient data.
"""

import asyncio
import os
import sys

# Ensure backend directory is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.config import settings
from app.knowledge import (
    KnowledgeDocument,
    KnowledgeIngestionPipeline,
    QdrantVectorStore,
    SourceType,
    get_embedding_service,
)
from app.logger import logger


async def main() -> None:
    logger.info("Starting Knowledge Base Ingestion Script...")

    # Validate production credentials if in production mode
    if settings.ENVIRONMENT == "production":
        if not settings.QDRANT_API_KEY:
            raise RuntimeError("Production ingestion halted: QDRANT_API_KEY environment variable is required in production.")
        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("Production ingestion halted: OPENAI_API_KEY environment variable is required in production.")

    # Create example reviewed document (Placeholders only)
    example_doc = KnowledgeDocument(
        document_id="doc-example-stress-management",
        title="Example Guidance on Deep Breathing Exercises",
        source_name="Public Health Educational Board",
        source_url="https://example.org/deep-breathing-guidance",
        source_type=SourceType.EDUCATIONAL_RESOURCE,
        publisher="Public Health Organization",
        topic="stress_management",
        content=(
            "Deep breathing exercises can help manage everyday stress and anxiety. "
            "Pursed-lip breathing and diaphragmatic breathing encourage full oxygen exchange "
            "and assist in lowering heart rate during moments of tension."
        ),
        version="1.0",
        reviewed=True,
    )

    # Use deterministic fake embeddings for local dev unless production keys exist
    force_fake = settings.ENVIRONMENT != "production"
    embedding_service = get_embedding_service(
        force_fake=force_fake,
        api_key=os.environ.get("OPENAI_API_KEY"),
    )
    vector_store = QdrantVectorStore()

    pipeline = KnowledgeIngestionPipeline(
        vector_store=vector_store,
        embedding_service=embedding_service,
    )

    result = await pipeline.ingest_document(example_doc)
    logger.info(f"Ingestion Complete: {result}")


if __name__ == "__main__":
    asyncio.run(main())
