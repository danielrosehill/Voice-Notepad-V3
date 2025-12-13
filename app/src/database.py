"""SQLite database for transcript history and analytics."""

import csv
import sqlite3
import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional


DB_DIR = Path.home() / ".config" / "voice-notepad-v3"
DB_FILE = DB_DIR / "transcriptions.db"
AUDIO_ARCHIVE_DIR = DB_DIR / "audio-archive"
CSV_EXPORT_FILE = DB_DIR / "transcription_history.csv"


@dataclass
class TranscriptionRecord:
    """A single transcription record."""
    id: Optional[int]
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
    prompt_text_length: int = 0  # Length of the system prompt sent

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "TranscriptionRecord":
        return cls(
            id=row["id"],
            timestamp=row["timestamp"],
            provider=row["provider"],
            model=row["model"],
            transcript_text=row["transcript_text"],
            audio_duration_seconds=row["audio_duration_seconds"],
            inference_time_ms=row["inference_time_ms"],
            input_tokens=row["input_tokens"],
            output_tokens=row["output_tokens"],
            estimated_cost=row["estimated_cost"],
            text_length=row["text_length"],
            word_count=row["word_count"],
            audio_file_path=row["audio_file_path"],
            vad_audio_duration_seconds=row["vad_audio_duration_seconds"],
            prompt_text_length=row["prompt_text_length"] if "prompt_text_length" in row.keys() else 0,
        )


class TranscriptionDB:
    """SQLite database for storing transcription history."""

    def __init__(self):
        DB_DIR.mkdir(parents=True, exist_ok=True)
        AUDIO_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection, creating if needed."""
        if self._conn is None:
            self._conn = sqlite3.connect(str(DB_FILE), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _init_db(self):
        """Initialize database schema."""
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS transcriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                transcript_text TEXT NOT NULL,
                audio_duration_seconds REAL,
                inference_time_ms INTEGER,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                estimated_cost REAL DEFAULT 0.0,
                text_length INTEGER DEFAULT 0,
                word_count INTEGER DEFAULT 0,
                audio_file_path TEXT,
                vad_audio_duration_seconds REAL,
                prompt_text_length INTEGER DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_timestamp ON transcriptions(timestamp);
            CREATE INDEX IF NOT EXISTS idx_provider ON transcriptions(provider);
        """)
        # Migrate existing tables to add new column if missing
        self._migrate_schema(conn)
        conn.commit()

    def _migrate_schema(self, conn):
        """Add any missing columns to existing tables."""
        cursor = conn.execute("PRAGMA table_info(transcriptions)")
        columns = {row[1] for row in cursor.fetchall()}

        if "prompt_text_length" not in columns:
            conn.execute("ALTER TABLE transcriptions ADD COLUMN prompt_text_length INTEGER DEFAULT 0")

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
    ) -> int:
        """Save a transcription and return its ID."""
        conn = self._get_conn()
        timestamp = datetime.now().isoformat()
        text_length = len(transcript_text)
        word_count = len(transcript_text.split())

        cursor = conn.execute(
            """
            INSERT INTO transcriptions (
                timestamp, provider, model, transcript_text,
                audio_duration_seconds, inference_time_ms,
                input_tokens, output_tokens, estimated_cost,
                text_length, word_count, audio_file_path,
                vad_audio_duration_seconds, prompt_text_length
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                timestamp, provider, model, transcript_text,
                audio_duration_seconds, inference_time_ms,
                input_tokens, output_tokens, estimated_cost,
                text_length, word_count, audio_file_path,
                vad_audio_duration_seconds, prompt_text_length,
            )
        )
        conn.commit()
        return cursor.lastrowid

    def get_transcription(self, id: int) -> Optional[TranscriptionRecord]:
        """Get a single transcription by ID."""
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT * FROM transcriptions WHERE id = ?",
            (id,)
        )
        row = cursor.fetchone()
        if row:
            return TranscriptionRecord.from_row(row)
        return None

    def get_transcriptions(
        self,
        limit: int = 50,
        offset: int = 0,
        search: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> list[TranscriptionRecord]:
        """Get transcriptions with pagination and optional filtering."""
        conn = self._get_conn()

        query = "SELECT * FROM transcriptions WHERE 1=1"
        params = []

        if search:
            query += " AND transcript_text LIKE ?"
            params.append(f"%{search}%")

        if provider:
            query += " AND provider = ?"
            params.append(provider)

        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor = conn.execute(query, params)
        return [TranscriptionRecord.from_row(row) for row in cursor.fetchall()]

    def get_total_count(self, search: Optional[str] = None, provider: Optional[str] = None) -> int:
        """Get total count of transcriptions (for pagination)."""
        conn = self._get_conn()

        query = "SELECT COUNT(*) FROM transcriptions WHERE 1=1"
        params = []

        if search:
            query += " AND transcript_text LIKE ?"
            params.append(f"%{search}%")

        if provider:
            query += " AND provider = ?"
            params.append(provider)

        cursor = conn.execute(query, params)
        return cursor.fetchone()[0]

    def delete_transcription(self, id: int) -> bool:
        """Delete a transcription by ID. Returns True if deleted."""
        conn = self._get_conn()

        # Get the record first to check for audio file
        record = self.get_transcription(id)
        if record and record.audio_file_path:
            audio_path = Path(record.audio_file_path)
            if audio_path.exists():
                audio_path.unlink()

        cursor = conn.execute(
            "DELETE FROM transcriptions WHERE id = ?",
            (id,)
        )
        conn.commit()
        return cursor.rowcount > 0

    def delete_all(self) -> int:
        """Delete all transcriptions. Returns count of deleted records."""
        conn = self._get_conn()

        # Delete audio files
        for audio_file in AUDIO_ARCHIVE_DIR.glob("*.opus"):
            audio_file.unlink()

        cursor = conn.execute("DELETE FROM transcriptions")
        conn.commit()
        return cursor.rowcount

    def get_storage_stats(self) -> dict:
        """Get storage statistics."""
        conn = self._get_conn()

        # Count records
        cursor = conn.execute("SELECT COUNT(*) FROM transcriptions")
        total_records = cursor.fetchone()[0]

        # Database file size
        db_size = DB_FILE.stat().st_size if DB_FILE.exists() else 0

        # Audio archive size
        audio_size = sum(f.stat().st_size for f in AUDIO_ARCHIVE_DIR.glob("*.opus"))

        # Count records with audio
        cursor = conn.execute(
            "SELECT COUNT(*) FROM transcriptions WHERE audio_file_path IS NOT NULL"
        )
        records_with_audio = cursor.fetchone()[0]

        return {
            "total_records": total_records,
            "records_with_audio": records_with_audio,
            "db_size_bytes": db_size,
            "audio_size_bytes": audio_size,
            "total_size_bytes": db_size + audio_size,
        }

    def get_model_performance(self) -> list[dict]:
        """Get aggregated performance statistics by provider/model."""
        conn = self._get_conn()

        cursor = conn.execute("""
            SELECT
                provider,
                model,
                COUNT(*) as count,
                AVG(inference_time_ms) as avg_inference_ms,
                AVG(CASE WHEN inference_time_ms > 0
                    THEN (text_length * 1000.0 / inference_time_ms)
                    ELSE NULL END) as avg_chars_per_sec,
                SUM(estimated_cost) as total_cost,
                AVG(audio_duration_seconds) as avg_audio_duration
            FROM transcriptions
            WHERE inference_time_ms IS NOT NULL
            GROUP BY provider, model
            ORDER BY count DESC
        """)

        return [
            {
                "provider": row["provider"],
                "model": row["model"],
                "count": row["count"],
                "avg_inference_ms": round(row["avg_inference_ms"] or 0, 1),
                "avg_chars_per_sec": round(row["avg_chars_per_sec"] or 0, 1),
                "total_cost": round(row["total_cost"] or 0, 4),
                "avg_audio_duration": round(row["avg_audio_duration"] or 0, 1),
            }
            for row in cursor.fetchall()
        ]

    def get_recent_stats(self, days: int = 7) -> dict:
        """Get statistics for recent days."""
        conn = self._get_conn()

        cursor = conn.execute("""
            SELECT
                COUNT(*) as count,
                SUM(estimated_cost) as total_cost,
                AVG(inference_time_ms) as avg_inference_ms,
                SUM(text_length) as total_chars,
                SUM(word_count) as total_words
            FROM transcriptions
            WHERE timestamp >= datetime('now', ?)
        """, (f"-{days} days",))

        row = cursor.fetchone()
        return {
            "count": row["count"] or 0,
            "total_cost": round(row["total_cost"] or 0, 4),
            "avg_inference_ms": round(row["avg_inference_ms"] or 0, 1),
            "total_chars": row["total_chars"] or 0,
            "total_words": row["total_words"] or 0,
        }

    def get_cost_this_hour(self) -> dict:
        """Get cost for the current hour."""
        conn = self._get_conn()
        cursor = conn.execute("""
            SELECT
                COUNT(*) as count,
                SUM(estimated_cost) as total_cost
            FROM transcriptions
            WHERE timestamp >= datetime('now', 'start of hour', 'localtime')
        """)
        row = cursor.fetchone()
        return {
            "count": row["count"] or 0,
            "total_cost": round(row["total_cost"] or 0, 6),
        }

    def get_cost_last_hour(self) -> dict:
        """Get cost for the previous hour."""
        conn = self._get_conn()
        cursor = conn.execute("""
            SELECT
                COUNT(*) as count,
                SUM(estimated_cost) as total_cost
            FROM transcriptions
            WHERE timestamp >= datetime('now', 'start of hour', '-1 hour', 'localtime')
              AND timestamp < datetime('now', 'start of hour', 'localtime')
        """)
        row = cursor.fetchone()
        return {
            "count": row["count"] or 0,
            "total_cost": round(row["total_cost"] or 0, 6),
        }

    def get_cost_today(self) -> dict:
        """Get cost for today (since midnight local time)."""
        conn = self._get_conn()
        cursor = conn.execute("""
            SELECT
                COUNT(*) as count,
                SUM(estimated_cost) as total_cost
            FROM transcriptions
            WHERE timestamp >= datetime('now', 'start of day', 'localtime')
        """)
        row = cursor.fetchone()
        return {
            "count": row["count"] or 0,
            "total_cost": round(row["total_cost"] or 0, 6),
        }

    def get_cost_this_week(self) -> dict:
        """Get cost for the current week (Monday to now)."""
        conn = self._get_conn()
        # SQLite weekday: 0 = Sunday, so Monday = -6 days from start of week
        cursor = conn.execute("""
            SELECT
                COUNT(*) as count,
                SUM(estimated_cost) as total_cost
            FROM transcriptions
            WHERE timestamp >= datetime('now', 'weekday 1', '-7 days', 'start of day', 'localtime')
        """)
        row = cursor.fetchone()
        return {
            "count": row["count"] or 0,
            "total_cost": round(row["total_cost"] or 0, 6),
        }

    def get_cost_all_time(self) -> dict:
        """Get total cost for all transcriptions."""
        conn = self._get_conn()
        cursor = conn.execute("""
            SELECT
                COUNT(*) as count,
                SUM(estimated_cost) as total_cost
            FROM transcriptions
        """)
        row = cursor.fetchone()
        return {
            "count": row["count"] or 0,
            "total_cost": round(row["total_cost"] or 0, 6),
        }

    def get_cost_this_month(self) -> dict:
        """Get cost for the current calendar month."""
        conn = self._get_conn()
        cursor = conn.execute("""
            SELECT
                COUNT(*) as count,
                SUM(estimated_cost) as total_cost
            FROM transcriptions
            WHERE timestamp >= datetime('now', 'start of month', 'localtime')
        """)
        row = cursor.fetchone()
        return {
            "count": row["count"] or 0,
            "total_cost": round(row["total_cost"] or 0, 6),
        }

    def get_cost_last_60_min(self) -> dict:
        """Get cost for the last 60 minutes."""
        conn = self._get_conn()
        cursor = conn.execute("""
            SELECT
                COUNT(*) as count,
                SUM(estimated_cost) as total_cost
            FROM transcriptions
            WHERE timestamp >= datetime('now', '-60 minutes', 'localtime')
        """)
        row = cursor.fetchone()
        return {
            "count": row["count"] or 0,
            "total_cost": round(row["total_cost"] or 0, 6),
        }

    def get_cost_by_provider(self) -> list[dict]:
        """Get cost breakdown by provider."""
        conn = self._get_conn()
        cursor = conn.execute("""
            SELECT
                provider,
                COUNT(*) as count,
                SUM(estimated_cost) as total_cost
            FROM transcriptions
            GROUP BY provider
            ORDER BY total_cost DESC
        """)
        return [
            {
                "provider": row["provider"],
                "count": row["count"],
                "total_cost": round(row["total_cost"] or 0, 6),
            }
            for row in cursor.fetchall()
        ]

    def get_cost_by_model(self) -> list[dict]:
        """Get cost breakdown by model."""
        conn = self._get_conn()
        cursor = conn.execute("""
            SELECT
                provider,
                model,
                COUNT(*) as count,
                SUM(estimated_cost) as total_cost
            FROM transcriptions
            GROUP BY provider, model
            ORDER BY total_cost DESC
        """)
        return [
            {
                "provider": row["provider"],
                "model": row["model"],
                "count": row["count"],
                "total_cost": round(row["total_cost"] or 0, 6),
            }
            for row in cursor.fetchall()
        ]

    def export_to_csv(
        self,
        filepath: Optional[Path] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> tuple[Path, int]:
        """Export transcriptions to a CSV file.

        Args:
            filepath: Output file path (defaults to config dir)
            start_date: ISO format start date filter (inclusive)
            end_date: ISO format end date filter (inclusive)

        Returns:
            Tuple of (filepath, record_count)
        """
        if filepath is None:
            filepath = CSV_EXPORT_FILE

        conn = self._get_conn()

        query = """
            SELECT
                timestamp,
                provider,
                model,
                transcript_text,
                audio_duration_seconds,
                vad_audio_duration_seconds,
                inference_time_ms,
                input_tokens,
                output_tokens,
                estimated_cost,
                word_count
            FROM transcriptions
            WHERE 1=1
        """
        params = []

        if start_date:
            query += " AND timestamp >= ?"
            params.append(start_date)

        if end_date:
            # Add one day to make end_date inclusive
            query += " AND timestamp < datetime(?, '+1 day')"
            params.append(end_date)

        query += " ORDER BY timestamp DESC"

        cursor = conn.execute(query, params)

        rows = cursor.fetchall()
        record_count = len(rows)

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
            for row in rows:
                writer.writerow([
                    row['timestamp'],
                    row['provider'],
                    row['model'],
                    row['transcript_text'],
                    row['audio_duration_seconds'],
                    row['vad_audio_duration_seconds'],
                    row['inference_time_ms'],
                    row['input_tokens'],
                    row['output_tokens'],
                    row['estimated_cost'],
                    row['word_count']
                ])

        return filepath, record_count

    def close(self):
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None


# Global instance
_db: Optional[TranscriptionDB] = None


def get_db() -> TranscriptionDB:
    """Get the global database instance."""
    global _db
    if _db is None:
        _db = TranscriptionDB()
    return _db
