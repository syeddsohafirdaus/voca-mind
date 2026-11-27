import abc
import asyncio
import json
import urllib.request
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



class OllamaEmbeddingService(BaseEmbeddingService):
    """Local semantic embeddings through Ollama."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        dimension: int | None = None,
        timeout: float | None = None,
    ) -> None:
        self.base_url = (
            base_url or settings.OLLAMA_BASE_URL
        ).rstrip("/")
        self.model = model or settings.OLLAMA_EMBEDDING_MODEL
        self.dimension = (
            dimension if dimension is not None
            else settings.EMBEDDING_DIMENSION
        )
        self.timeout = (
            timeout if timeout is not None
            else settings.OLLAMA_EMBEDDING_TIMEOUT_SECONDS
        )

    def _request_embeddings(
        self, texts: List[str]
    ) -> List[List[float]]:
        payload = {
            "model": self.model,
            "input": texts,
        }

        request = urllib.request.Request(
            self.base_url + "/api/embed",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(
            request, timeout=self.timeout
        ) as response:
            result = json.load(response)

        vectors = result.get("embeddings")

        if not isinstance(vectors, list):
            raise ValueError("Invalid Ollama embedding response.")

        if len(vectors) != len(texts):
            raise ValueError("Embedding count mismatch.")

        for vector in vectors:
            if not isinstance(vector, list):
                raise ValueError("Invalid embedding vector.")

            if len(vector) != self.dimension:
                raise ValueError("Embedding dimension mismatch.")

            if not all(
                isinstance(value, (int, float))
                and math.isfinite(value)
                for value in vector
            ):
                raise ValueError("Invalid embedding values.")

        return vectors

    async def embed_text(self, text: str) -> List[float]:
        clean_text = self.validate_text(text)

        vectors = await asyncio.to_thread(
            self._request_embeddings,
            ["search_query: " + clean_text],
        )

        return vectors[0]

    async def embed_batch(
        self, texts: List[str]
    ) -> List[List[float]]:
        if not texts:
            return []

        clean_texts = [
            "search_document: " + self.validate_text(text)
            for text in texts
        ]

        return await asyncio.to_thread(
            self._request_embeddings,
            clean_texts,
        )


def get_embedding_service(
    force_fake: bool = False,
    api_key: str | None = None,
) -> BaseEmbeddingService:
    """Return the configured embedding provider."""

    provider = settings.EMBEDDING_PROVIDER.strip().lower()

    if force_fake:
        return DeterministicFakeEmbeddingService(
            dimension=settings.EMBEDDING_DIMENSION
        )

    if provider == "ollama":
        return OllamaEmbeddingService()

    if provider == "fake":
        if settings.ENVIRONMENT == "production":
            raise RuntimeError(
                "Fake embeddings are not allowed in production."
            )

        return DeterministicFakeEmbeddingService(
            dimension=settings.EMBEDDING_DIMENSION
        )

    if provider == "openai":
        key = api_key or settings.OPENAI_API_KEY

        if not key:
            raise RuntimeError(
                "OpenAI embedding API key is not configured."
            )

        return OpenAIEmbeddingService(
            api_key=key,
            model=settings.EMBEDDING_MODEL,
            dimension=settings.EMBEDDING_DIMENSION,
        )

    if provider == "auto":
        if api_key:
            return OpenAIEmbeddingService(
                api_key=api_key,
                model=settings.EMBEDDING_MODEL,
                dimension=settings.EMBEDDING_DIMENSION,
            )

        if settings.ENVIRONMENT == "production":
            raise RuntimeError(
                "Configure a real embedding provider."
            )

        return DeterministicFakeEmbeddingService(
            dimension=settings.EMBEDDING_DIMENSION
        )

    raise ValueError(
        f"Unsupported embedding provider: {provider}"
    )
