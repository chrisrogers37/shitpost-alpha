"""
OpenAI Embedding Client

Generates text embeddings via the OpenAI embeddings API for semantic
similarity search in the Historical Echoes feature.
"""

from openai import OpenAI

from shit.config.shitpost_settings import settings
from shit.logging import get_service_logger

logger = get_service_logger("embeddings")

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536


class EmbeddingClient:
    """Client for generating text embeddings via OpenAI API."""

    def __init__(self, model: str = EMBEDDING_MODEL):
        self.model = model
        self._client = OpenAI(api_key=settings.OPENAI_API_KEY)

    def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text.

        Args:
            text: Text to embed.

        Returns:
            List of floats (1536 dimensions).
        """
        text = text[:8000]
        response = self._client.embeddings.create(
            model=self.model,
            input=text,
        )
        return response.data[0].embedding

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts.

        Args:
            texts: List of texts to embed (max 2048 per API call).

        Returns:
            List of embedding vectors, one per input text.
        """
        if not texts:
            return []

        truncated = [t[:8000] for t in texts]
        response = self._client.embeddings.create(
            model=self.model,
            input=truncated,
        )
        return [item.embedding for item in response.data]
