"""Shared Qdrant client management."""

from pathlib import Path
from threading import RLock

from qdrant_client import QdrantClient
from app.config import settings


_client = None
_lock = RLock()


def get_local_qdrant_client() -> QdrantClient:
    """Return one persistent local client per process."""
    global _client

    with _lock:
        if _client is not None:
            return _client

        if not settings.QDRANT_LOCAL_PATH.strip():
            raise ValueError(
                "QDRANT_LOCAL_PATH must be configured."
            )

        path = Path(
            settings.QDRANT_LOCAL_PATH
        ).expanduser().resolve()

        path.mkdir(
            parents=True,
            exist_ok=True,
            mode=0o700,
        )

        _client = QdrantClient(path=str(path))

        return _client


def close_local_qdrant_client() -> None:
    """Close the shared client and release storage locks."""
    global _client

    with _lock:
        if _client is not None:
            _client.close()
            _client = None
