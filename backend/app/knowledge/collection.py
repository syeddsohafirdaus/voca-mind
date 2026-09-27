from typing import Any
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from app.config import settings
from app.logger import logger


def ensure_collection(
    client: Any,
    collection_name: str = settings.QDRANT_COLLECTION_NAME,
    dimension: int = settings.EMBEDDING_DIMENSION,
    distance: str = "Cosine",
) -> bool:
    """Idempotently inspects and creates Qdrant collection if missing.

    Safety:
    - Never drops or recreates an existing collection.
    - Safe to execute repeatedly during application startup.
    """
    try:
        # Check if collection exists
        if hasattr(client, "collection_exists"):
            exists = client.collection_exists(collection_name)
        else:
            # Fallback for mock or older client versions
            collections = client.get_collections().collections
            exists = any(c.name == collection_name for c in collections)

        if exists:
            logger.info(f"Qdrant collection '{collection_name}' already exists.")
            return True

        # Determine distance enum
        distance_enum = (
            qmodels.Distance.COSINE
            if distance.lower() == "cosine"
            else qmodels.Distance.DOT
        )

        # Create collection
        client.create_collection(
            collection_name=collection_name,
            vectors_config=qmodels.VectorParams(
                size=dimension,
                distance=distance_enum,
            ),
        )
        logger.info(f"Created Qdrant collection '{collection_name}' with size={dimension}, distance={distance}.")
        return True
    except Exception as e:
        logger.error(f"Error ensuring Qdrant collection '{collection_name}': {str(e)}")
        raise
