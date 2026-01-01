"""Embedding client for semantic search using Gemini text-embedding-004.

Gemini text-embedding-004 is free (1500 RPM, no cost per token).
"""

import hashlib
import logging
import threading
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple

# Reuse the SDK import pattern from transcription.py
try:
    from google import genai
    from google.genai import types as genai_types
    GEMINI_SDK_AVAILABLE = True
except ImportError:
    genai = None
    genai_types = None
    GEMINI_SDK_AVAILABLE = False

logger = logging.getLogger(__name__)

# Constants
EMBEDDING_MODEL = "text-embedding-004"
EMBEDDING_DIMENSIONS = 768  # Good balance of quality and storage (~3KB per transcript)
EMBEDDING_BATCH_SIZE = 100  # Process embeddings in batches of 100


@dataclass
class EmbeddingResult:
    """Result from embedding API."""
    embeddings: List[List[float]]  # List of embedding vectors
    input_tokens: int = 0
    model: str = EMBEDDING_MODEL


class GeminiEmbeddingClient:
    """Google Gemini embedding client using text-embedding-004.

    This model is completely free with 1500 requests per minute.
    """

    def __init__(self, api_key: str, model: str = EMBEDDING_MODEL, dimensions: int = EMBEDDING_DIMENSIONS):
        self.api_key = api_key
        self.model = model
        self.dimensions = dimensions
        self._client = None
        self._lock = threading.Lock()

    def _get_client(self):
        """Lazy-load the Gemini client."""
        if self._client is None:
            with self._lock:
                if self._client is None:
                    if not GEMINI_SDK_AVAILABLE:
                        raise ImportError("google-genai package not installed. Run: pip install google-genai")
                    self._client = genai.Client(api_key=self.api_key)
        return self._client

    def embed_text(self, text: str) -> List[float]:
        """Embed a single text string.

        Args:
            text: The text to embed

        Returns:
            768-dimensional embedding vector
        """
        result = self.embed_texts([text])
        return result.embeddings[0] if result.embeddings else []

    def embed_texts(self, texts: List[str]) -> EmbeddingResult:
        """Embed multiple texts in a single API call.

        Args:
            texts: List of texts to embed

        Returns:
            EmbeddingResult with list of embedding vectors
        """
        if not texts:
            return EmbeddingResult(embeddings=[], input_tokens=0)

        client = self._get_client()

        try:
            # Use RETRIEVAL_DOCUMENT for stored documents (transcripts)
            # Use RETRIEVAL_QUERY for search queries
            response = client.models.embed_content(
                model=self.model,
                contents=texts,
                config=genai_types.EmbedContentConfig(
                    task_type="RETRIEVAL_DOCUMENT",
                    output_dimensionality=self.dimensions,
                ),
            )

            # Extract embeddings from response
            embeddings = []
            for emb in response.embeddings:
                embeddings.append(list(emb.values))

            # Note: text-embedding-004 is free, no token tracking needed
            return EmbeddingResult(
                embeddings=embeddings,
                input_tokens=0,  # Free model, no cost tracking
                model=self.model,
            )

        except Exception as e:
            logger.error(f"Embedding API error: {e}")
            raise

    def embed_query(self, query: str) -> List[float]:
        """Embed a search query (uses RETRIEVAL_QUERY task type).

        Args:
            query: The search query to embed

        Returns:
            768-dimensional embedding vector
        """
        if not query:
            return []

        client = self._get_client()

        try:
            response = client.models.embed_content(
                model=self.model,
                contents=[query],
                config=genai_types.EmbedContentConfig(
                    task_type="RETRIEVAL_QUERY",
                    output_dimensionality=self.dimensions,
                ),
            )

            if response.embeddings:
                return list(response.embeddings[0].values)
            return []

        except Exception as e:
            logger.error(f"Query embedding error: {e}")
            raise


def compute_text_hash(text: str) -> str:
    """Compute MD5 hash of text for change detection."""
    return hashlib.md5(text.encode('utf-8')).hexdigest()


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors.

    Args:
        a: First embedding vector
        b: Second embedding vector

    Returns:
        Similarity score between -1 and 1 (higher = more similar)
    """
    if not a or not b or len(a) != len(b):
        return 0.0

    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot / (norm_a * norm_b)


def search_similar(
    query_embedding: List[float],
    embeddings: List[dict],
    top_k: int = 20,
    min_similarity: float = 0.3,
) -> List[Tuple[str, float]]:
    """Find top_k most similar transcripts.

    Args:
        query_embedding: Embedding of the search query
        embeddings: List of dicts with 'transcript_id' and 'embedding' keys
        top_k: Maximum number of results to return
        min_similarity: Minimum similarity threshold (0-1)

    Returns:
        List of (transcript_id, similarity_score) tuples, sorted by similarity
    """
    if not query_embedding or not embeddings:
        return []

    scores = []
    for emb in embeddings:
        if 'embedding' not in emb or 'transcript_id' not in emb:
            continue
        sim = cosine_similarity(query_embedding, emb['embedding'])
        if sim >= min_similarity:
            scores.append((emb['transcript_id'], sim))

    # Sort by similarity (highest first)
    scores.sort(key=lambda x: x[1], reverse=True)

    return scores[:top_k]


# Singleton client instance
_embedding_client: Optional[GeminiEmbeddingClient] = None
_client_lock = threading.Lock()


def get_embedding_client(api_key: str) -> GeminiEmbeddingClient:
    """Get or create singleton embedding client.

    Args:
        api_key: Gemini API key

    Returns:
        GeminiEmbeddingClient instance
    """
    global _embedding_client
    if _embedding_client is None:
        with _client_lock:
            if _embedding_client is None:
                _embedding_client = GeminiEmbeddingClient(api_key)
    return _embedding_client
