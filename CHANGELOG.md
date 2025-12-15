# Changelog

All notable changes to Voice Notepad will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.5.0] - 2025-12-15

### Added
- **Full-Text Search (FTS5)**: Automatic SQLite FTS5 indexing for fast transcript searching
  - Automatically enabled on all new and existing databases
  - Significantly faster search queries on large databases (hundreds/thousands of transcriptions)
  - Seamlessly falls back to LIKE queries if FTS is unavailable
- **Database Tab in Settings**: New dedicated tab showing database statistics
  - Total transcription count
  - Database size and archived audio size
  - FTS status indicator
  - "Optimize Database (VACUUM)" button to reclaim disk space
  - "Refresh Statistics" button to update numbers
- **Delete All History Button**: Red button in History tab header
  - Comprehensive warning dialog showing what will be deleted
  - Automatically runs VACUUM after deletion to reclaim disk space
  - Success notification with deletion count
- **VACUUM Operation**: Database optimization to reclaim unused space
  - Especially useful after deleting many transcriptions
  - Can be triggered manually from Settings → Database tab
  - Automatically runs after "Delete All History"

### Changed
- Search queries now use FTS5 MATCH when Full-Text Search is enabled (much faster)
- Database initialization now automatically enables FTS on first run

### Technical
- Added `vacuum()`, `enable_fts()`, and `is_fts_enabled()` methods to TranscriptionDB
- FTS5 virtual table with automatic sync triggers for INSERT, UPDATE, DELETE
- Database tab UI in Settings with live statistics
- Updated History widget with delete all functionality

## [1.4.0] - 2024-12-14

### Added
- File transcription feature - transcribe audio files directly
- Multiple file selection support
- File transcription tab in main UI

### Changed
- Improved audio processing pipeline
- Better error handling for microphone disconnections

## [1.3.0] - 2024-12-13

### Added
- Initial public release
- Multi-provider support (OpenRouter, Gemini, OpenAI, Mistral)
- Global hotkey support with multiple modes
- Voice Activity Detection (VAD)
- Automatic Gain Control (AGC)
- Cost tracking and analytics
- Transcript history with search
- Audio archival in Opus format

[1.5.0]: https://github.com/danielrosehill/Voice-Notepad/releases/tag/v1.5.0
[1.4.0]: https://github.com/danielrosehill/Voice-Notepad/releases/tag/v1.4.0
[1.3.0]: https://github.com/danielrosehill/Voice-Notepad/releases/tag/v1.3.0
