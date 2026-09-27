import abc
import hashlib
import math
from typing import List
from app.config import settings


class BaseEmbeddingService(abc.ABC):
    """Abstract base class for vector embedding services."""

    def validate_text(self, text: str) -> str:
        """Validates that input text is non-empty and non-whitespace."""
        if not text or not text.strip():
            raise ValueError("Text content cannot be empty or blank.")
        return text.strip()

    @abc.abstractmethod
    async def embed_text(self, text: str) -> List[float]:
        """Asynchronously converts a single text string into a float vector."""
        pass

    @abc.abstractmethod
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Asynchronously converts a batch of text strings into float vectors."""
        pass


class DeterministicFakeEmbeddingService(BaseEmbeddingService):
    """Deterministic fake embedding service for offline testing and local development.

    Same input text always produces the exact same normalized float vector of length `dimension`.
    Does NOT make external network calls or require API keys.
    """

    def __init__(self, dimension: int = settings.EMBEDDING_DIMENSION) -> None:
        self.dimension = dimension

    def _hash_to_vector(self, text: str) -> List[float]:
        """Generates a deterministic normalized unit vector from input text."""
        clean_text = self.validate_text(text)
        
        # Generate 64-byte SHA512 hash sequence
        raw_hash = hashlib.sha512(clean_text.encode("utf-8")).digest()
        
        vector = []
        for i in range(self.dimension):
            # Derive deterministic float for index i using hash bytes & index offset
            byte_idx = (i * 3) % len(raw_hash)
            val = (raw_hash[byte_idx] ^ (i & 0xFF)) / 255.0 - 0.5
            vector.append(val)
        
        # Normalize vector to unit length (Euclidean norm)
        norm = math.sqrt(sum(v * v for v in vector))
        if norm == 0:
            return [1.0 / math.sqrt(self.dimension)] * self.dimension
        return [v / norm for v in vector]

    async def embed_text(self, text: str) -> List[float]:
        """Asynchronously produces a deterministic vector for single text input."""
        return self._hash_to_vector(text)

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Asynchronously produces deterministic vectors for a list of text inputs."""
        if not texts:
            return []
        return [self._hash_to_vector(text) for text in texts]


class OpenAIEmbeddingService(BaseEmbeddingService):
    """OpenAI API embedding provider using OpenAI SDK."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = settings.EMBEDDING_MODEL,
        dimension: int = settings.EMBEDDING_DIMENSION,
    ) -> None:
        self.model = model
        self.dimension = dimension
        self.api_key = api_key
        self._client = None

    def _get_client(self):
        if self._client is None:
            import openai
            self._client = openai.AsyncOpenAI(api_key=self.api_key)
        return self._client

    async def embed_text(self, text: str) -> List[float]:
        clean_text = self.validate_text(text)
        client = self._get_client()
        response = await client.embeddings.create(
            input=clean_text,
            model=self.model,
        )
        return response.data[0].embedding

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        clean_texts = [self.validate_text(t) for t in texts]
        client = self._get_client()
        response = await client.embeddings.create(
            input=clean_texts,
            model=self.model,
        )
        return [item.embedding for item in response.data]


def get_embedding_service(
    force_fake: bool = False,
    api_key: str | None = None,
) -> BaseEmbeddingService:
    """Factory function returning active embedding service instance."""
    if force_fake or not api_key:
        return DeterministicFakeEmbeddingService(dimension=settings.EMBEDDING_DIMENSION)
    return OpenAIEmbeddingService(api_key=api_key, model=settings.EMBEDDING_MODEL)
