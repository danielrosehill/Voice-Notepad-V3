"""Migration script from SQLite to Mongita.

This script:
1. Reads all data from the existing SQLite database
2. Converts it to Mongita format
3. Writes to the new Mongita database
4. Backs up the old SQLite database
5. Can be run safely multiple times (idempotent)
"""

import sqlite3
from pathlib import Path
from datetime import datetime
import shutil

# Import both old and new database modules
from database import DB_FILE, TranscriptionRecord as SQLiteRecord
from database_mongo import get_db, MONGO_DIR


def migrate_sqlite_to_mongita(backup: bool = True) -> dict:
    """Migrate SQLite database to Mongita.

    Args:
        backup: If True, backup SQLite database before migration

    Returns:
        dict with migration statistics
    """
    stats = {
        "transcriptions_migrated": 0,
        "transcriptions_skipped": 0,
        "errors": [],
        "backup_path": None,
    }

    # Check if SQLite database exists
    if not DB_FILE.exists():
        stats["errors"].append("SQLite database not found")
        return stats

    # Backup SQLite database
    if backup:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = DB_FILE.parent / f"transcriptions_sqlite_backup_{timestamp}.db"
        shutil.copy2(DB_FILE, backup_path)
        stats["backup_path"] = str(backup_path)
        print(f"✓ Backed up SQLite database to: {backup_path}")

    # Connect to SQLite
    conn = sqlite3.connect(str(DB_FILE))
    conn.row_factory = sqlite3.Row

    # Get Mongita database
    mongo_db = get_db()

    try:
        # Migrate transcriptions
        cursor = conn.execute("SELECT * FROM transcriptions ORDER BY timestamp ASC")

        for row in cursor:
            try:
                # Check if already migrated (by timestamp and text)
                existing = list(mongo_db._get_db().transcriptions.find({
                    'timestamp': row['timestamp'],
                    'transcript_text': row['transcript_text']
                }).limit(1))

                if existing:
                    stats["transcriptions_skipped"] += 1
                    continue

                # Convert SQLite row to dict
                record = SQLiteRecord.from_row(row)

                # Save to Mongita (id will be auto-generated)
                mongo_db.save_transcription(
                    provider=record.provider,
                    model=record.model,
                    transcript_text=record.transcript_text,
                    audio_duration_seconds=record.audio_duration_seconds,
                    inference_time_ms=record.inference_time_ms,
                    input_tokens=record.input_tokens,
                    output_tokens=record.output_tokens,
                    estimated_cost=record.estimated_cost,
                    audio_file_path=record.audio_file_path,
                    vad_audio_duration_seconds=record.vad_audio_duration_seconds,
                    prompt_text_length=record.prompt_text_length,
                    source=record.source,
                    source_path=record.source_path,
                )

                stats["transcriptions_migrated"] += 1

            except Exception as e:
                stats["errors"].append(f"Error migrating row {row.get('id', 'unknown')}: {e}")

        print(f"✓ Migrated {stats['transcriptions_migrated']} transcriptions")
        print(f"  Skipped {stats['transcriptions_skipped']} duplicates")

    except Exception as e:
        stats["errors"].append(f"Migration failed: {e}")
        raise

    finally:
        conn.close()

    return stats


def verify_migration() -> dict:
    """Verify migration completed successfully.

    Returns:
        dict with verification results
    """
    results = {
        "sqlite_count": 0,
        "mongita_count": 0,
        "match": False,
    }

    # Count SQLite records
    if DB_FILE.exists():
        conn = sqlite3.connect(str(DB_FILE))
        cursor = conn.execute("SELECT COUNT(*) FROM transcriptions")
        results["sqlite_count"] = cursor.fetchone()[0]
        conn.close()

    # Count Mongita records
    mongo_db = get_db()
    results["mongita_count"] = mongo_db._get_db().transcriptions.count_documents({})

    results["match"] = results["sqlite_count"] == results["mongita_count"]

    return results


if __name__ == "__main__":
    print("=" * 60)
    print("SQLite to Mongita Migration")
    print("=" * 60)

    # Run migration
    print("\nStarting migration...")
    stats = migrate_sqlite_to_mongita(backup=True)

    print("\n" + "=" * 60)
    print("Migration Summary")
    print("=" * 60)
    print(f"Transcriptions migrated: {stats['transcriptions_migrated']}")
    print(f"Transcriptions skipped:  {stats['transcriptions_skipped']}")

    if stats['backup_path']:
        print(f"Backup saved to:         {stats['backup_path']}")

    if stats['errors']:
        print(f"\nErrors ({len(stats['errors'])}):")
        for error in stats['errors']:
            print(f"  - {error}")

    # Verify migration
    print("\n" + "=" * 60)
    print("Verification")
    print("=" * 60)
    verification = verify_migration()
    print(f"SQLite records:  {verification['sqlite_count']}")
    print(f"Mongita records: {verification['mongita_count']}")
    print(f"Match:           {verification['match']}")

    if verification['match']:
        print("\n✓ Migration successful!")
    else:
        print("\n✗ Migration verification failed - record counts don't match")

    print("\n" + "=" * 60)
    print("Next Steps")
    print("=" * 60)
    print("1. Test the app with: ./run.sh")
    print("2. Verify all features work correctly")
    print("3. If everything works, you can safely delete the SQLite backup")
    print(f"   rm {stats.get('backup_path', 'transcriptions_sqlite_backup_*.db')}")
    print("=" * 60)
