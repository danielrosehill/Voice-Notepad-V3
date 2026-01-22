"""Mongita database for transcript history, prompts, and settings.

This replaces the SQLite database with Mongita (pure Python MongoDB implementation).
Provides identical API to the old database.py for easy migration.
"""

import csv
import threading
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any

from mongita import MongitaClientDisk

# Preview length for recent panel (characters) - full text stored, preview truncated
TRANSCRIPT_PREVIEW_LENGTH = 200


# Database directory
DB_DIR = Path.home() / ".config" / "voice-notepad-v3"
MONGO_DIR = DB_DIR / "mongita"
AUDIO_ARCHIVE_DIR = DB_DIR / "audio-archive"
CSV_EXPORT_FILE = DB_DIR / "transcription_history.csv"


@dataclass
class TranscriptionRecord:
    """A single transcription record."""
    id: Optional[str]  # MongoDB _id as string
    timestamp: str
    provider: str
    model: str
    transcript_text: str
    audio_duration_seconds: Optional[float]
    inference_time_ms: Optional[int]
    input_tokens: int
    output_tokens: int
    estimated_cost: float
    text_length: int
    word_count: int
    audio_file_path: Optional[str]
    vad_audio_duration_seconds: Optional[float]
    prompt_text_length: int = 0
    source: str = "recording"  # "recording" or "file"
    source_path: Optional[str] = None

    def to_dict(self):
        """Convert to dict for MongoDB storage."""
        d = asdict(self)
        # Remove id if None (let MongoDB generate _id)
        if d.get('id') is None:
            d.pop('id', None)
        return d

    @classmethod
    def from_doc(cls, doc: Dict[str, Any]) -> "TranscriptionRecord":
        """Create from MongoDB document."""
        # Convert _id to string id
        doc_copy = doc.copy()
        if '_id' in doc_copy:
            doc_copy['id'] = str(doc_copy['_id'])
            del doc_copy['_id']

        # Provide defaults for optional fields
        defaults = {
            'audio_duration_seconds': None,
            'inference_time_ms': None,
            'input_tokens': 0,
            'output_tokens': 0,
            'estimated_cost': 0.0,
            'text_length': 0,
            'word_count': 0,
            'audio_file_path': None,
            'vad_audio_duration_seconds': None,
            'prompt_text_length': 0,
            'source': 'recording',
            'source_path': None,
        }

        for key, default_val in defaults.items():
            if key not in doc_copy:
                doc_copy[key] = default_val

        return cls(**doc_copy)


class TranscriptionDB:
    """Mongita database for storing transcription history and prompts.

    Collections:
    - transcriptions: Transcription history (replaces SQLite table)
    - prompts: Prompt library (new)

    Thread-safe: all operations are protected by a lock.

    Performance optimizations:
    - All-time stats are cached with a 60-second TTL to avoid full collection scans
    - Recent panel queries use projection to limit data transfer
    """

    # Cache TTL for all-time stats (seconds)
    STATS_CACHE_TTL = 60.0

    def __init__(self):
        MONGO_DIR.mkdir(parents=True, exist_ok=True)
        AUDIO_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

        self._client: Optional[MongitaClientDisk] = None
        self._db = None
        self._lock = threading.RLock()

        # Cache for all-time stats (avoids full collection scan on every call)
        self._all_time_stats_cache: Optional[Dict[str, Any]] = None
        self._all_time_stats_timestamp: float = 0.0

        self._init_db()

    def _get_db(self):
        """Get database connection, creating if needed."""
        if self._client is None:
            self._client = MongitaClientDisk(str(MONGO_DIR))
            self._db = self._client.voice_notepad
        return self._db

    def _init_db(self):
        """Initialize database and indexes."""
        with self._lock:
            db = self._get_db()

            # Transcriptions collection indexes
            transcriptions = db.transcriptions
            transcriptions.create_index('timestamp')
            transcriptions.create_index('provider')
            transcriptions.create_index('source')

            # Text search index (Mongita supports text indexes)
            try:
                transcriptions.create_index([('transcript_text', 'text')])
            except Exception:
                # Text indexes may not be fully supported, fallback to regex search
                pass

            # Prompts collection indexes
            prompts = db.prompts
            prompts.create_index('category')
            prompts.create_index('is_enabled')
            prompts.create_index('is_builtin')
            prompts.create_index('priority')

            # Embeddings collection indexes (for semantic search)
            embeddings = db.embeddings
            embeddings.create_index('transcript_id')
            embeddings.create_index('text_hash')
            embeddings.create_index('created_at')

    def save_transcription(
        self,
        provider: str,
        model: str,
        transcript_text: str,
        audio_duration_seconds: Optional[float] = None,
        inference_time_ms: Optional[int] = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        estimated_cost: float = 0.0,
        audio_file_path: Optional[str] = None,
        vad_audio_duration_seconds: Optional[float] = None,
        prompt_text_length: int = 0,
        source: str = "recording",
        source_path: Optional[str] = None,
    ) -> str:
        """Save a transcription and return its ID as string."""
        with self._lock:
            db = self._get_db()
            timestamp = datetime.now().isoformat()
            text_length = len(transcript_text)
            word_count = len(transcript_text.split())

            doc = {
                'timestamp': timestamp,
                'provider': provider,
                'model': model,
                'transcript_text': transcript_text,
                'audio_duration_seconds': audio_duration_seconds,
                'inference_time_ms': inference_time_ms,
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'estimated_cost': estimated_cost,
                'text_length': text_length,
                'word_count': word_count,
                'audio_file_path': audio_file_path,
                'vad_audio_duration_seconds': vad_audio_duration_seconds,
                'prompt_text_length': prompt_text_length,
                'source': source,
                'source_path': source_path,
            }

            result = db.transcriptions.insert_one(doc)

            # Invalidate stats cache since we added a new transcription
            self._all_time_stats_cache = None
            self._all_time_stats_timestamp = 0.0

            return str(result.inserted_id)

    def get_transcription(self, id: str) -> Optional[TranscriptionRecord]:
        """Get a single transcription by ID."""
        with self._lock:
            db = self._get_db()
            from bson import ObjectId

            try:
                doc = db.transcriptions.find_one({'_id': ObjectId(id)})
                if doc:
                    return TranscriptionRecord.from_doc(doc)
            except Exception:
                # Invalid ObjectId format
                pass
            return None

    def get_recent_transcriptions(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get the most recent transcriptions for quick access panel.

        Returns lightweight dicts with just the fields needed for display:
        - id: Transcript ID as string
        - transcript_text: Full text for copy functionality
        - transcript_preview: Truncated preview (first N chars) for display
        - timestamp: ISO timestamp
        - word_count: Word count
        - model: Model used

        Args:
            limit: Maximum number of transcriptions to return (default 5)

        Returns:
            List of dicts sorted by timestamp descending (most recent first)
        """
        with self._lock:
            db = self._get_db()

            # Note: Mongita doesn't support projection in find(), so we fetch all fields
            # but only extract the ones we need for the result dict
            cursor = db.transcriptions.find({}).sort([('timestamp', -1)]).limit(limit)

            results = []
            for doc in cursor:
                full_text = doc.get('transcript_text', '')
                # Truncate for preview display (UI shows this)
                preview = full_text[:TRANSCRIPT_PREVIEW_LENGTH]
                if len(full_text) > TRANSCRIPT_PREVIEW_LENGTH:
                    preview += '...'

                results.append({
                    'id': str(doc.get('_id', '')),
                    'transcript_text': full_text,  # Full text for copy functionality
                    'transcript_preview': preview,  # Truncated for display
                    'timestamp': doc.get('timestamp', ''),
                    'word_count': doc.get('word_count', 0),
                    'model': doc.get('model', ''),
                })

            return results

    def get_transcriptions(
        self,
        limit: int = 50,
        offset: int = 0,
        search: Optional[str] = None,
        provider: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> List[TranscriptionRecord]:
        """Get transcriptions with pagination and optional filtering.

        Args:
            limit: Maximum number of records to return
            offset: Number of records to skip
            search: Optional text search (regex)
            provider: Optional provider filter
            date_from: Optional start date (ISO format: YYYY-MM-DD)
            date_to: Optional end date (ISO format: YYYY-MM-DD)
        """
        with self._lock:
            db = self._get_db()

            query = {}

            if search:
                # Use regex search for text matching
                query['transcript_text'] = {'$regex': search, '$options': 'i'}

            if provider:
                query['provider'] = provider

            # Date filtering
            if date_from or date_to:
                timestamp_query = {}
                if date_from:
                    # Start of day
                    timestamp_query['$gte'] = f"{date_from}T00:00:00"
                if date_to:
                    # End of day
                    timestamp_query['$lte'] = f"{date_to}T23:59:59"
                query['timestamp'] = timestamp_query

            cursor = db.transcriptions.find(query).sort('timestamp', -1).skip(offset).limit(limit)
            return [TranscriptionRecord.from_doc(doc) for doc in cursor]

    def get_total_count(
        self,
        search: Optional[str] = None,
        provider: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> int:
        """Get total count of transcriptions (for pagination)."""
        with self._lock:
            db = self._get_db()

            query = {}

            if search:
                query['transcript_text'] = {'$regex': search, '$options': 'i'}

            if provider:
                query['provider'] = provider

            # Date filtering
            if date_from or date_to:
                timestamp_query = {}
                if date_from:
                    timestamp_query['$gte'] = f"{date_from}T00:00:00"
                if date_to:
                    timestamp_query['$lte'] = f"{date_to}T23:59:59"
                query['timestamp'] = timestamp_query

            return db.transcriptions.count_documents(query)

    def delete_transcription(self, id: str) -> bool:
        """Delete a transcription by ID. Returns True if deleted."""
        with self._lock:
            db = self._get_db()
            from bson import ObjectId

            try:
                # Get the record first to check for audio file
                doc = db.transcriptions.find_one({'_id': ObjectId(id)})
                if doc and doc.get('audio_file_path'):
                    audio_path = Path(doc['audio_file_path'])
                    if audio_path.exists():
                        audio_path.unlink()

                result = db.transcriptions.delete_one({'_id': ObjectId(id)})
                if result.deleted_count > 0:
                    # Invalidate stats cache
                    self._all_time_stats_cache = None
                    self._all_time_stats_timestamp = 0.0
                    return True
                return False
            except Exception:
                return False

    def delete_all(self) -> int:
        """Delete all transcriptions. Returns count of deleted records."""
        with self._lock:
            db = self._get_db()

            # Delete audio files
            for audio_file in AUDIO_ARCHIVE_DIR.glob("*.opus"):
                audio_file.unlink()

            result = db.transcriptions.delete_many({})

            # Invalidate stats cache
            self._all_time_stats_cache = None
            self._all_time_stats_timestamp = 0.0

            return result.deleted_count

    def get_storage_stats(self) -> dict:
        """Get storage statistics."""
        with self._lock:
            db = self._get_db()

            # Count records
            total_records = db.transcriptions.count_documents({})

            # Database directory size (Mongita uses multiple files)
            db_size = sum(f.stat().st_size for f in MONGO_DIR.rglob('*') if f.is_file())

            # Audio archive size
            audio_size = sum(f.stat().st_size for f in AUDIO_ARCHIVE_DIR.glob("*.opus"))

            # Count records with audio
            records_with_audio = db.transcriptions.count_documents(
                {'audio_file_path': {'$ne': None}}
            )

            return {
                "total_records": total_records,
                "records_with_audio": records_with_audio,
                "db_size_bytes": db_size,
                "audio_size_bytes": audio_size,
                "total_size_bytes": db_size + audio_size,
            }

    def get_model_performance(self) -> List[dict]:
        """Get aggregated performance statistics by provider/model."""
        with self._lock:
            db = self._get_db()

            # Mongita doesn't support aggregate, so use find + manual grouping
            query = {'inference_time_ms': {'$ne': None}}
            results = list(db.transcriptions.find(query))

            # Group by provider and model manually
            grouped = {}
            for r in results:
                key = (r.get('provider', 'unknown'), r.get('model', 'unknown'))
                if key not in grouped:
                    grouped[key] = {
                        'count': 0,
                        'total_inference_ms': 0,
                        'total_cost': 0,
                        'total_audio_duration': 0,
                        'total_text_length': 0,
                    }

                grouped[key]['count'] += 1
                grouped[key]['total_inference_ms'] += r.get('inference_time_ms') or 0
                grouped[key]['total_cost'] += r.get('estimated_cost') or 0
                grouped[key]['total_audio_duration'] += r.get('audio_duration_seconds') or 0
                grouped[key]['total_text_length'] += r.get('text_length') or 0

            # Convert to output format and sort by count
            output = []
            for (provider, model), stats in grouped.items():
                count = stats['count']
                avg_inference_ms = stats['total_inference_ms'] / count if count > 0 else 0
                avg_audio_duration = stats['total_audio_duration'] / count if count > 0 else 0
                avg_chars_per_sec = (stats['total_text_length'] * 1000.0 / stats['total_inference_ms']) if stats['total_inference_ms'] > 0 else 0

                output.append({
                    "provider": provider,
                    "model": model,
                    "count": count,
                    "avg_inference_ms": round(avg_inference_ms, 1),
                    "avg_chars_per_sec": round(avg_chars_per_sec, 1),
                    "total_cost": round(stats['total_cost'], 4),
                    "avg_audio_duration": round(avg_audio_duration, 1),
                })

            # Sort by count descending
            output.sort(key=lambda x: x['count'], reverse=True)
            return output

    def get_recent_stats(self, days: int = 7) -> dict:
        """Get statistics for recent days."""
        with self._lock:
            db = self._get_db()

            cutoff = (datetime.now() - timedelta(days=days)).isoformat()

            # Mongita doesn't support aggregate, so use find + manual calculation
            query = {'timestamp': {'$gte': cutoff}}
            results = list(db.transcriptions.find(query))

            if results:
                count = len(results)
                total_cost = sum((r.get('estimated_cost') or 0) for r in results)
                inference_times = [(r.get('inference_time_ms') or 0) for r in results if r.get('inference_time_ms')]
                avg_inference_ms = sum(inference_times) / len(inference_times) if inference_times else 0
                total_chars = sum((r.get('text_length') or 0) for r in results)
                total_words = sum((r.get('word_count') or 0) for r in results)

                return {
                    "count": count,
                    "total_cost": round(total_cost, 4),
                    "avg_inference_ms": round(avg_inference_ms, 1),
                    "total_chars": total_chars,
                    "total_words": total_words,
                }

            return {
                "count": 0,
                "total_cost": 0,
                "avg_inference_ms": 0,
                "total_chars": 0,
                "total_words": 0,
            }

    def _get_cost_stats(self, query: Dict[str, Any]) -> dict:
        """Helper to get cost statistics for a query."""
        with self._lock:
            db = self._get_db()

            # Mongita doesn't support aggregate, so use find + manual sum
            results = list(db.transcriptions.find(query))

            if results:
                count = len(results)
                total_cost = sum((r.get('estimated_cost') or 0) for r in results)
                return {
                    "count": count,
                    "total_cost": round(total_cost, 6),
                }

            return {"count": 0, "total_cost": 0}

    def get_cost_today(self) -> dict:
        """Get cost for today (since midnight local time)."""
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        return self._get_cost_stats({'timestamp': {'$gte': today_start}})

    def get_cost_this_hour(self) -> dict:
        """Get cost for the current hour."""
        hour_start = datetime.now().replace(minute=0, second=0, microsecond=0).isoformat()
        return self._get_cost_stats({'timestamp': {'$gte': hour_start}})

    def get_cost_last_hour(self) -> dict:
        """Get cost for the previous hour."""
        now = datetime.now()
        last_hour_start = (now - timedelta(hours=1)).replace(minute=0, second=0, microsecond=0).isoformat()
        this_hour_start = now.replace(minute=0, second=0, microsecond=0).isoformat()

        return self._get_cost_stats({
            'timestamp': {
                '$gte': last_hour_start,
                '$lt': this_hour_start
            }
        })

    def get_cost_this_week(self) -> dict:
        """Get cost for the current week (Monday to now)."""
        now = datetime.now()
        # Get Monday of current week
        monday = now - timedelta(days=now.weekday())
        week_start = monday.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

        return self._get_cost_stats({'timestamp': {'$gte': week_start}})

    def get_cost_this_month(self) -> dict:
        """Get cost for the current calendar month."""
        month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
        return self._get_cost_stats({'timestamp': {'$gte': month_start}})

    def get_cost_last_60_min(self) -> dict:
        """Get cost for the last 60 minutes."""
        cutoff = (datetime.now() - timedelta(minutes=60)).isoformat()
        return self._get_cost_stats({'timestamp': {'$gte': cutoff}})

    def get_cost_all_time(self) -> dict:
        """Get total cost for all transcriptions."""
        return self._get_cost_stats({})

    def get_all_time_stats(self) -> dict:
        """Get all-time statistics including word count.

        Returns dict with keys: count, total_words, total_chars, total_cost

        Performance: Results are cached for STATS_CACHE_TTL seconds to avoid
        full collection scans on every UI update.
        """
        current_time = time.time()

        # Check cache validity
        if (
            self._all_time_stats_cache is not None
            and (current_time - self._all_time_stats_timestamp) < self.STATS_CACHE_TTL
        ):
            return self._all_time_stats_cache

        with self._lock:
            db = self._get_db()

            # Note: Mongita doesn't support projection, so we fetch all fields
            # but only use the ones we need for aggregation
            results = list(db.transcriptions.find({}))

            if results:
                count = len(results)
                total_words = sum((r.get('word_count') or 0) for r in results)
                total_chars = sum((r.get('text_length') or 0) for r in results)
                total_cost = sum((r.get('estimated_cost') or 0) for r in results)

                stats = {
                    "count": count,
                    "total_words": total_words,
                    "total_chars": total_chars,
                    "total_cost": round(total_cost, 4),
                }
            else:
                stats = {
                    "count": 0,
                    "total_words": 0,
                    "total_chars": 0,
                    "total_cost": 0,
                }

            # Update cache
            self._all_time_stats_cache = stats
            self._all_time_stats_timestamp = current_time

            return stats

    def invalidate_stats_cache(self):
        """Invalidate the all-time stats cache.

        Call this after adding/deleting transcriptions to ensure
        fresh stats on next query.
        """
        self._all_time_stats_cache = None
        self._all_time_stats_timestamp = 0.0

    def get_daily_cost_breakdown(self, days: int = 30) -> List[dict]:
        """Get cost breakdown by day for the last N days.

        Returns list of dicts with keys: date, count, cost, avg_cost
        Sorted by date descending (most recent first).
        """
        with self._lock:
            db = self._get_db()

            cutoff = (datetime.now() - timedelta(days=days)).isoformat()
            results = list(db.transcriptions.find({'timestamp': {'$gte': cutoff}}))

            # Group by date
            from collections import defaultdict
            daily = defaultdict(lambda: {'count': 0, 'cost': 0.0})

            for r in results:
                date_str = r['timestamp'][:10]  # YYYY-MM-DD
                daily[date_str]['count'] += 1
                daily[date_str]['cost'] += r.get('estimated_cost') or 0

            # Convert to list and calculate averages
            output = []
            for date_str, stats in daily.items():
                avg = stats['cost'] / stats['count'] if stats['count'] > 0 else 0
                output.append({
                    'date': date_str,
                    'count': stats['count'],
                    'cost': round(stats['cost'], 6),
                    'avg_cost': round(avg, 6),
                })

            # Sort by date descending
            output.sort(key=lambda x: x['date'], reverse=True)
            return output

    def get_cost_by_provider(self) -> List[dict]:
        """Get cost breakdown by provider."""
        with self._lock:
            db = self._get_db()

            # Mongita doesn't support aggregate, so use find + manual grouping
            results = list(db.transcriptions.find({}))

            # Group by provider manually
            grouped = {}
            for r in results:
                provider = r.get('provider', 'unknown')
                if provider not in grouped:
                    grouped[provider] = {'count': 0, 'total_cost': 0}

                grouped[provider]['count'] += 1
                grouped[provider]['total_cost'] += r.get('estimated_cost') or 0

            # Convert to output format and sort by total_cost descending
            output = [
                {
                    "provider": provider,
                    "count": stats['count'],
                    "total_cost": round(stats['total_cost'], 6),
                }
                for provider, stats in grouped.items()
            ]
            output.sort(key=lambda x: x['total_cost'], reverse=True)
            return output

    def get_cost_by_model(self) -> List[dict]:
        """Get cost breakdown by model."""
        with self._lock:
            db = self._get_db()

            # Mongita doesn't support aggregate, so use find + manual grouping
            results = list(db.transcriptions.find({}))

            # Group by provider and model manually
            grouped = {}
            for r in results:
                key = (r.get('provider', 'unknown'), r.get('model', 'unknown'))
                if key not in grouped:
                    grouped[key] = {'count': 0, 'total_cost': 0}

                grouped[key]['count'] += 1
                grouped[key]['total_cost'] += r.get('estimated_cost') or 0

            # Convert to output format and sort by total_cost descending
            output = [
                {
                    "provider": provider,
                    "model": model,
                    "count": stats['count'],
                    "total_cost": round(stats['total_cost'], 6),
                }
                for (provider, model), stats in grouped.items()
            ]
            output.sort(key=lambda x: x['total_cost'], reverse=True)
            return output

    def export_to_csv(
        self,
        filepath: Optional[Path] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> tuple[Path, int]:
        """Export transcriptions to a CSV file."""
        if filepath is None:
            filepath = CSV_EXPORT_FILE

        with self._lock:
            db = self._get_db()

            query = {}

            if start_date:
                query['timestamp'] = {'$gte': start_date}

            if end_date:
                # Add one day to make end_date inclusive
                end_dt = datetime.fromisoformat(end_date) + timedelta(days=1)
                if 'timestamp' in query:
                    query['timestamp']['$lt'] = end_dt.isoformat()
                else:
                    query['timestamp'] = {'$lt': end_dt.isoformat()}

            cursor = db.transcriptions.find(query).sort('timestamp', -1)
            docs = list(cursor)

        record_count = len(docs)

        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Timestamp',
                'Provider',
                'Model',
                'Transcript',
                'Audio Duration (s)',
                'VAD Duration (s)',
                'Inference Time (ms)',
                'Input Tokens',
                'Output Tokens',
                'Estimated Cost',
                'Word Count'
            ])
            for doc in docs:
                writer.writerow([
                    doc.get('timestamp'),
                    doc.get('provider'),
                    doc.get('model'),
                    doc.get('transcript_text'),
                    doc.get('audio_duration_seconds'),
                    doc.get('vad_audio_duration_seconds'),
                    doc.get('inference_time_ms'),
                    doc.get('input_tokens'),
                    doc.get('output_tokens'),
                    doc.get('estimated_cost'),
                    doc.get('word_count')
                ])

        return filepath, record_count

    def vacuum(self) -> bool:
        """Optimize database (Mongita equivalent of SQLite VACUUM).

        For Mongita, this:
        1. Rebuilds indexes
        2. Removes orphaned audio files
        3. Returns statistics

        Returns True if successful.
        """
        with self._lock:
            try:
                db = self._get_db()

                # Rebuild indexes (drop and recreate)
                transcriptions = db.transcriptions

                # Get index info first
                existing_indexes = list(transcriptions.list_indexes())

                # Drop non-_id indexes
                for idx in existing_indexes:
                    if idx['name'] != '_id_':
                        try:
                            transcriptions.drop_index(idx['name'])
                        except Exception:
                            pass  # Index may already be dropped or doesn't exist

                # Recreate indexes
                transcriptions.create_index('timestamp')
                transcriptions.create_index('provider')
                transcriptions.create_index('source')

                try:
                    transcriptions.create_index([('transcript_text', 'text')])
                except Exception:
                    pass  # Text indexes may not be fully supported in Mongita

                # Clean up orphaned audio files
                self._cleanup_orphaned_audio()

                return True
            except Exception as e:
                print(f"Optimization failed: {e}")
                return False

    def _cleanup_orphaned_audio(self):
        """Remove audio files that have no corresponding database record."""
        with self._lock:
            db = self._get_db()

            # Get all audio file paths from database
            cursor = db.transcriptions.find(
                {'audio_file_path': {'$ne': None}},
                {'audio_file_path': 1}
            )
            db_audio_paths = {doc.get('audio_file_path') for doc in cursor if doc.get('audio_file_path')}

            # Get all audio files on disk
            disk_audio_files = set(str(f) for f in AUDIO_ARCHIVE_DIR.glob("*.opus"))

            # Find orphaned files
            orphaned = disk_audio_files - db_audio_paths

            # Delete orphaned files
            for orphan_path in orphaned:
                try:
                    Path(orphan_path).unlink()
                    print(f"Deleted orphaned audio file: {orphan_path}")
                except Exception as e:
                    print(f"Could not delete {orphan_path}: {e}")

    def is_fts_enabled(self) -> bool:
        """Check if Full-Text Search is enabled.

        For Mongita, text indexes may be limited. This checks if a text index exists.
        """
        with self._lock:
            try:
                db = self._get_db()
                indexes = list(db.transcriptions.list_indexes())

                # Check if any index is a text index
                for idx in indexes:
                    if 'text' in idx.get('key', []):
                        return True
                return False
            except Exception:
                return False

    # ===== PROMPT LIBRARY OPERATIONS =====

    def save_prompt(self, prompt_doc: Dict[str, Any]) -> str:
        """Save a prompt template and return its ID."""
        with self._lock:
            db = self._get_db()

            # Add timestamps if not present
            if 'created_at' not in prompt_doc:
                prompt_doc['created_at'] = datetime.now().isoformat()
            prompt_doc['modified_at'] = datetime.now().isoformat()

            # If _id is provided, do upsert
            if '_id' in prompt_doc:
                result = db.prompts.replace_one(
                    {'_id': prompt_doc['_id']},
                    prompt_doc,
                    upsert=True
                )
                return str(prompt_doc['_id'])
            else:
                result = db.prompts.insert_one(prompt_doc)
                return str(result.inserted_id)

    def get_prompt(self, prompt_id: str) -> Optional[Dict[str, Any]]:
        """Get a single prompt by ID."""
        with self._lock:
            db = self._get_db()
            from bson import ObjectId

            try:
                doc = db.prompts.find_one({'_id': ObjectId(prompt_id)})
                if doc:
                    doc['id'] = str(doc['_id'])
                    del doc['_id']
                return doc
            except Exception:
                return None

    def get_prompts(
        self,
        category: Optional[str] = None,
        is_enabled: Optional[bool] = None,
        is_builtin: Optional[bool] = None,
        search: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get prompts with optional filtering."""
        with self._lock:
            db = self._get_db()

            query = {}

            if category:
                query['category'] = category

            if is_enabled is not None:
                query['is_enabled'] = is_enabled

            if is_builtin is not None:
                query['is_builtin'] = is_builtin

            if search:
                # Search in name, description, or tags
                query['$or'] = [
                    {'name': {'$regex': search, '$options': 'i'}},
                    {'description': {'$regex': search, '$options': 'i'}},
                    {'tags': {'$regex': search, '$options': 'i'}},
                ]

            cursor = db.prompts.find(query).sort('priority', 1)  # Sort by priority ascending
            prompts = []
            for doc in cursor:
                doc['id'] = str(doc['_id'])
                del doc['_id']
                prompts.append(doc)

            return prompts

    def get_enabled_prompts(self, categories: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Get all enabled prompts, optionally filtered by categories."""
        with self._lock:
            db = self._get_db()

            query = {'is_enabled': True}

            if categories:
                query['category'] = {'$in': categories}

            cursor = db.prompts.find(query).sort('priority', 1)
            prompts = []
            for doc in cursor:
                doc['id'] = str(doc['_id'])
                del doc['_id']
                prompts.append(doc)

            return prompts

    def update_prompt(self, prompt_id: str, updates: Dict[str, Any]) -> bool:
        """Update a prompt. Returns True if successful."""
        with self._lock:
            db = self._get_db()
            from bson import ObjectId

            try:
                updates['modified_at'] = datetime.now().isoformat()
                result = db.prompts.update_one(
                    {'_id': ObjectId(prompt_id)},
                    {'$set': updates}
                )
                return result.modified_count > 0
            except Exception:
                return False

    def delete_prompt(self, prompt_id: str) -> bool:
        """Delete a prompt by ID. Returns True if deleted."""
        with self._lock:
            db = self._get_db()
            from bson import ObjectId

            try:
                result = db.prompts.delete_one({'_id': ObjectId(prompt_id)})
                return result.deleted_count > 0
            except Exception:
                return False

    def get_prompt_categories(self) -> List[str]:
        """Get list of unique prompt categories."""
        with self._lock:
            db = self._get_db()
            return db.prompts.distinct('category')

    def close(self):
        """Close database connection."""
        # Mongita doesn't require explicit close, but we'll clean up references
        self._client = None
        self._db = None

    # ===== SETTINGS OPERATIONS =====
    # Settings are stored as a single document in the 'settings' collection.
    # This provides more robustness than JSON files (atomic writes, no corruption on crash).

    def get_settings(self) -> Dict[str, Any]:
        """Get all settings as a dictionary.

        Returns empty dict if no settings exist yet.
        """
        with self._lock:
            db = self._get_db()
            doc = db.settings.find_one({'_id': 'user_settings'})
            if doc:
                # Remove internal fields
                doc.pop('_id', None)
                doc.pop('_schema_version', None)
                return doc
            return {}

    def save_settings(self, settings: Dict[str, Any]) -> bool:
        """Save all settings (full replacement).

        Args:
            settings: Dictionary of all settings to save

        Returns:
            True if successful
        """
        with self._lock:
            db = self._get_db()
            doc = settings.copy()
            doc['_id'] = 'user_settings'
            doc['_schema_version'] = 1
            doc['_modified_at'] = datetime.now().isoformat()

            try:
                db.settings.replace_one(
                    {'_id': 'user_settings'},
                    doc,
                    upsert=True
                )
                return True
            except Exception as e:
                print(f"Failed to save settings: {e}")
                return False

    def update_settings(self, updates: Dict[str, Any]) -> bool:
        """Update specific settings (partial update).

        Args:
            updates: Dictionary of settings to update

        Returns:
            True if successful
        """
        with self._lock:
            db = self._get_db()
            updates['_modified_at'] = datetime.now().isoformat()

            try:
                result = db.settings.update_one(
                    {'_id': 'user_settings'},
                    {'$set': updates},
                    upsert=True
                )
                return True
            except Exception as e:
                print(f"Failed to update settings: {e}")
                return False

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a single setting value.

        Args:
            key: Setting key name
            default: Default value if key doesn't exist

        Returns:
            The setting value or default
        """
        settings = self.get_settings()
        return settings.get(key, default)

    def set_setting(self, key: str, value: Any) -> bool:
        """Set a single setting value.

        Args:
            key: Setting key name
            value: Value to set

        Returns:
            True if successful
        """
        return self.update_settings({key: value})

    def delete_setting(self, key: str) -> bool:
        """Delete a single setting.

        Args:
            key: Setting key name to delete

        Returns:
            True if successful
        """
        with self._lock:
            db = self._get_db()
            try:
                result = db.settings.update_one(
                    {'_id': 'user_settings'},
                    {'$unset': {key: ''}}
                )
                return True
            except Exception as e:
                print(f"Failed to delete setting: {e}")
                return False

    def settings_exist(self) -> bool:
        """Check if settings document exists in database."""
        with self._lock:
            db = self._get_db()
            return db.settings.count_documents({'_id': 'user_settings'}) > 0


# Global instance with thread-safe initialization
_db: Optional[TranscriptionDB] = None
_db_lock = threading.Lock()


def get_db() -> TranscriptionDB:
    """Get the global database instance (thread-safe)."""
    global _db
    if _db is None:
        with _db_lock:
            # Double-check after acquiring lock
            if _db is None:
                _db = TranscriptionDB()
    return _db
