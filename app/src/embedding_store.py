"""Embedding storage and batch processing for semantic search.

Embeddings are stored in a separate Mongita collection and processed in batches
to avoid excessive API calls. Batch processing occurs every 100 new transcripts.
"""

import logging
import threading
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any

from .embeddings import (
    GeminiEmbeddingClient,
    compute_text_hash,
    cosine_similarity,
    EMBEDDING_BATCH_SIZE,
    EMBEDDING_DIMENSIONS,
)

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingRecord:
    """A single embedding record."""
    id: Optional[str]
    transcript_id: str
    embedding: List[float]
    text_hash: str
    model: str
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for MongoDB storage."""
        d = {
            'transcript_id': self.transcript_id,
            'embedding': self.embedding,
            'text_hash': self.text_hash,
            'model': self.model,
            'created_at': self.created_at,
        }
        return d

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]) -> "EmbeddingRecord":
        """Create from MongoDB document."""
        return cls(
            id=str(doc.get('_id', '')),
            transcript_id=doc.get('transcript_id', ''),
            embedding=doc.get('embedding', []),
            text_hash=doc.get('text_hash', ''),
            model=doc.get('model', ''),
            created_at=doc.get('created_at', ''),
        )


class EmbeddingStore:
    """Manages embedding storage and retrieval.

    Uses the same Mongita database as TranscriptionDB but with separate collections:
    - embeddings: Stores embedding vectors linked to transcript IDs
    - embedding_batches: Tracks batch processing status

    Thread-safe: all operations are protected by a lock.
    """

    def __init__(self, db):
        """Initialize with existing database connection.

        Args:
            db: The Mongita database object (from TranscriptionDB._get_db())
        """
        self._db = db
        self._lock = threading.RLock()
        self._init_collections()

    def _init_collections(self):
        """Initialize embedding collections and indexes."""
        with self._lock:
            # Embeddings collection
            embeddings = self._db.embeddings
            embeddings.create_index('transcript_id')
            embeddings.create_index('text_hash')
            embeddings.create_index('created_at')

            # Batch tracking collection
            batches = self._db.embedding_batches
            batches.create_index('status')
            batches.create_index('created_at')

    def save_embedding(
        self,
        transcript_id: str,
        embedding: List[float],
        text_hash: str,
        model: str = "text-embedding-004",
    ) -> str:
        """Save an embedding for a transcript.

        Args:
            transcript_id: ID of the transcription record
            embedding: The embedding vector
            text_hash: MD5 hash of the transcript text
            model: Model used for embedding

        Returns:
            The embedding record ID
        """
        with self._lock:
            doc = {
                'transcript_id': transcript_id,
                'embedding': embedding,
                'text_hash': text_hash,
                'model': model,
                'created_at': datetime.now().isoformat(),
            }
            result = self._db.embeddings.insert_one(doc)
            return str(result.inserted_id)

    def save_embeddings_batch(
        self,
        records: List[Tuple[str, List[float], str]],
        model: str = "text-embedding-004",
    ) -> int:
        """Save multiple embeddings at once.

        Args:
            records: List of (transcript_id, embedding, text_hash) tuples
            model: Model used for embedding

        Returns:
            Number of embeddings saved
        """
        if not records:
            return 0

        with self._lock:
            docs = [
                {
                    'transcript_id': transcript_id,
                    'embedding': embedding,
                    'text_hash': text_hash,
                    'model': model,
                    'created_at': datetime.now().isoformat(),
                }
                for transcript_id, embedding, text_hash in records
            ]
            result = self._db.embeddings.insert_many(docs)
            return len(result.inserted_ids)

    def get_embedding(self, transcript_id: str) -> Optional[EmbeddingRecord]:
        """Get embedding for a specific transcript.

        Args:
            transcript_id: ID of the transcription record

        Returns:
            EmbeddingRecord or None if not found
        """
        with self._lock:
            doc = self._db.embeddings.find_one({'transcript_id': transcript_id})
            if doc:
                return EmbeddingRecord.from_doc(doc)
            return None

    def get_all_embeddings(self) -> List[Dict[str, Any]]:
        """Get all embeddings for similarity search.

        Returns:
            List of dicts with 'transcript_id' and 'embedding' keys
        """
        with self._lock:
            cursor = self._db.embeddings.find({}, {'transcript_id': 1, 'embedding': 1})
            return [
                {
                    'transcript_id': doc['transcript_id'],
                    'embedding': doc['embedding'],
                }
                for doc in cursor
            ]

    def has_embedding(self, transcript_id: str) -> bool:
        """Check if a transcript has an embedding.

        Args:
            transcript_id: ID of the transcription record

        Returns:
            True if embedding exists
        """
        with self._lock:
            return self._db.embeddings.count_documents({'transcript_id': transcript_id}) > 0

    def needs_update(self, transcript_id: str, current_text_hash: str) -> bool:
        """Check if an embedding needs to be updated (text changed).

        Args:
            transcript_id: ID of the transcription record
            current_text_hash: MD5 hash of current transcript text

        Returns:
            True if embedding doesn't exist or text has changed
        """
        with self._lock:
            doc = self._db.embeddings.find_one(
                {'transcript_id': transcript_id},
                {'text_hash': 1}
            )
            if not doc:
                return True  # No embedding exists
            return doc.get('text_hash') != current_text_hash

    def delete_embedding(self, transcript_id: str) -> bool:
        """Delete embedding for a transcript.

        Args:
            transcript_id: ID of the transcription record

        Returns:
            True if deleted
        """
        with self._lock:
            result = self._db.embeddings.delete_one({'transcript_id': transcript_id})
            return result.deleted_count > 0

    def get_unembedded_transcript_ids(self, limit: int = EMBEDDING_BATCH_SIZE) -> List[str]:
        """Get transcript IDs that don't have embeddings yet.

        Args:
            limit: Maximum number of IDs to return

        Returns:
            List of transcript IDs without embeddings
        """
        with self._lock:
            # Get all transcript IDs
            all_transcripts = list(
                self._db.transcriptions.find({}, {'_id': 1}).sort('timestamp', 1).limit(limit * 2)
            )
            all_ids = {str(doc['_id']) for doc in all_transcripts}

            # Get transcript IDs that have embeddings
            embedded = list(
                self._db.embeddings.find({}, {'transcript_id': 1})
            )
            embedded_ids = {doc['transcript_id'] for doc in embedded}

            # Return IDs without embeddings
            unembedded = [tid for tid in all_ids if tid not in embedded_ids]

            # Sort by original order and limit
            return unembedded[:limit]

    def get_embedding_count(self) -> int:
        """Get total number of embeddings stored."""
        with self._lock:
            return self._db.embeddings.count_documents({})

    def get_transcript_count(self) -> int:
        """Get total number of transcripts."""
        with self._lock:
            return self._db.transcriptions.count_documents({})

    def get_unembedded_count(self) -> int:
        """Get count of transcripts without embeddings."""
        total = self.get_transcript_count()
        embedded = self.get_embedding_count()
        return max(0, total - embedded)

    def needs_batch_processing(self) -> bool:
        """Check if we have enough unembedded transcripts for a batch.

        Returns:
            True if >= EMBEDDING_BATCH_SIZE transcripts need embedding
        """
        return self.get_unembedded_count() >= EMBEDDING_BATCH_SIZE

    def get_stats(self) -> Dict[str, Any]:
        """Get embedding statistics.

        Returns:
            Dict with total_transcripts, total_embeddings, pending_count
        """
        total = self.get_transcript_count()
        embedded = self.get_embedding_count()
        return {
            'total_transcripts': total,
            'total_embeddings': embedded,
            'pending_count': max(0, total - embedded),
            'coverage_percent': round(embedded / total * 100, 1) if total > 0 else 0,
        }

    # ===== Similarity Search =====

    def search_similar(
        self,
        query_embedding: List[float],
        top_k: int = 20,
        min_similarity: float = 0.3,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> List[Tuple[str, float]]:
        """Search for similar transcripts.

        Args:
            query_embedding: Embedding of the search query
            top_k: Maximum number of results
            min_similarity: Minimum cosine similarity threshold (0-1)
            date_from: Optional start date filter (ISO format)
            date_to: Optional end date filter (ISO format)

        Returns:
            List of (transcript_id, similarity_score) tuples
        """
        if not query_embedding:
            return []

        # Get all embeddings
        all_embeddings = self.get_all_embeddings()

        if not all_embeddings:
            return []

        # If date filters, get valid transcript IDs
        valid_ids = None
        if date_from or date_to:
            valid_ids = self._get_transcript_ids_in_range(date_from, date_to)
            if not valid_ids:
                return []

        # Calculate similarities
        scores = []
        for emb in all_embeddings:
            if valid_ids is not None and emb['transcript_id'] not in valid_ids:
                continue

            sim = cosine_similarity(query_embedding, emb['embedding'])
            if sim >= min_similarity:
                scores.append((emb['transcript_id'], sim))

        # Sort by similarity (highest first)
        scores.sort(key=lambda x: x[1], reverse=True)

        return scores[:top_k]

    def _get_transcript_ids_in_range(
        self,
        date_from: Optional[str],
        date_to: Optional[str],
    ) -> set:
        """Get transcript IDs within a date range.

        Args:
            date_from: Start date (ISO format)
            date_to: End date (ISO format)

        Returns:
            Set of transcript IDs
        """
        with self._lock:
            query = {}

            if date_from:
                query['timestamp'] = {'$gte': date_from}

            if date_to:
                if 'timestamp' in query:
                    query['timestamp']['$lte'] = date_to
                else:
                    query['timestamp'] = {'$lte': date_to}

            cursor = self._db.transcriptions.find(query, {'_id': 1})
            return {str(doc['_id']) for doc in cursor}


class BatchEmbeddingProcessor:
    """Processes embeddings in batches in a background thread."""

    def __init__(
        self,
        embedding_client: GeminiEmbeddingClient,
        embedding_store: EmbeddingStore,
        db,
    ):
        """Initialize batch processor.

        Args:
            embedding_client: Client for calling embedding API
            embedding_store: Store for saving embeddings
            db: Database connection for reading transcripts
        """
        self.client = embedding_client
        self.store = embedding_store
        self.db = db
        self._processing = False
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None

    def is_processing(self) -> bool:
        """Check if a batch is currently being processed."""
        with self._lock:
            return self._processing

    def process_batch_async(self, callback=None):
        """Start batch processing in a background thread.

        Args:
            callback: Optional function to call when complete (receives count or error)
        """
        if self.is_processing():
            if callback:
                callback(0, "Already processing")
            return

        with self._lock:
            self._processing = True

        def _run():
            try:
                count = self._process_batch()
                if callback:
                    callback(count, None)
            except Exception as e:
                logger.error(f"Batch embedding failed: {e}")
                if callback:
                    callback(0, str(e))
            finally:
                with self._lock:
                    self._processing = False

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def _process_batch(self) -> int:
        """Process a batch of transcripts.

        Returns:
            Number of embeddings created
        """
        # Get unembedded transcript IDs
        transcript_ids = self.store.get_unembedded_transcript_ids(EMBEDDING_BATCH_SIZE)

        if not transcript_ids:
            return 0

        logger.info(f"Processing batch of {len(transcript_ids)} transcripts")

        # Get transcript texts from database
        from bson import ObjectId
        texts_to_embed = []
        id_hash_pairs = []

        for tid in transcript_ids:
            try:
                doc = self.db.transcriptions.find_one({'_id': ObjectId(tid)})
                if doc and doc.get('transcript_text'):
                    text = doc['transcript_text']
                    text_hash = compute_text_hash(text)
                    texts_to_embed.append(text)
                    id_hash_pairs.append((tid, text_hash))
            except Exception as e:
                logger.warning(f"Failed to get transcript {tid}: {e}")

        if not texts_to_embed:
            return 0

        # Call embedding API
        try:
            result = self.client.embed_texts(texts_to_embed)
            embeddings = result.embeddings
        except Exception as e:
            logger.error(f"Embedding API call failed: {e}")
            raise

        if len(embeddings) != len(id_hash_pairs):
            logger.error(f"Embedding count mismatch: got {len(embeddings)}, expected {len(id_hash_pairs)}")
            return 0

        # Save embeddings
        records = [
            (tid, emb, text_hash)
            for (tid, text_hash), emb in zip(id_hash_pairs, embeddings)
        ]
        count = self.store.save_embeddings_batch(records)

        logger.info(f"Saved {count} embeddings")
        return count


# Singleton instances
_embedding_store: Optional[EmbeddingStore] = None
_batch_processor: Optional[BatchEmbeddingProcessor] = None
_store_lock = threading.Lock()


def get_embedding_store() -> Optional[EmbeddingStore]:
    """Get the global embedding store instance.

    Returns None if database is not initialized.
    """
    global _embedding_store
    if _embedding_store is None:
        with _store_lock:
            if _embedding_store is None:
                try:
                    from .database_mongo import get_db
                    db = get_db()._get_db()
                    _embedding_store = EmbeddingStore(db)
                except Exception as e:
                    logger.error(f"Failed to initialize embedding store: {e}")
                    return None
    return _embedding_store


def get_batch_processor(api_key: str) -> Optional[BatchEmbeddingProcessor]:
    """Get the global batch processor instance.

    Args:
        api_key: Gemini API key for embedding client

    Returns None if initialization fails.
    """
    global _batch_processor
    if _batch_processor is None:
        with _store_lock:
            if _batch_processor is None:
                try:
                    store = get_embedding_store()
                    if store is None:
                        return None

                    from .embeddings import GeminiEmbeddingClient
                    from .database_mongo import get_db
                    client = GeminiEmbeddingClient(api_key)
                    db = get_db()._get_db()
                    _batch_processor = BatchEmbeddingProcessor(client, store, db)
                except Exception as e:
                    logger.error(f"Failed to initialize batch processor: {e}")
                    return None
    return _batch_processor
