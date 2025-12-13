# Features

## Core Features

### Single-Pass Transcription

Voice Notepad sends audio directly to multimodal AI models along with a cleanup prompt. The model handles both transcription and text cleanup simultaneously, returning polished, formatted text.

This approach:

- **Reduces latency** - One API call instead of two
- **Better context** - The model "hears" the original audio
- **Verbal instructions** - Say "delete that" or "new paragraph" and the AI understands

### Multiple AI Providers

Access various AI providers through a unified interface:

- **OpenRouter** (recommended) - Single API key for multiple models
- **Gemini** - Direct Google AI access
- **OpenAI** - GPT-4o audio models
- **Mistral** - Voxtral speech models

### Markdown Output

Transcriptions are formatted as markdown with:

- Proper punctuation and sentences
- Natural paragraph spacing
- Subheadings for longer content
- Full markdown rendering in the app

## Productivity Features

### Global Hotkeys

Control recording from anywhere on your desktop, even when the app is minimized:

| Default Key | Action |
|-------------|--------|
| F14 | Start recording |
| F15 | Stop recording (discard) |
| F16 | Stop & transcribe |

Configure in **Settings > Hotkeys**. F14-F20 (macro keys) are recommended to avoid conflicts.

### System Tray

The app minimizes to the system tray for quick access:

- Click to show/hide
- Right-click for quick actions
- Always available for recording

### Transcript History

All transcriptions are automatically saved to a local SQLite database with:

- Timestamp and provider/model used
- Audio duration (original and after VAD)
- Token usage and estimated cost
- Full text searchable

Browse history in the **History** tab.

## Cost Management

### Cost Tracking

Monitor your API spending with detailed breakdowns:

- **Daily/weekly/monthly** spend tracking
- **Model breakdown** - See which models cost most
- **Balance display** - Real-time OpenRouter credit balance

OpenRouter provides the most accurate cost data via its API.

### Voice Activity Detection (VAD)

Reduce costs by removing silence before upload:

- Automatic speech segment detection
- Strips silence from recordings
- Smaller files = lower API costs
- Uses [Silero VAD](https://github.com/snakers4/silero-vad)

Enable in **Settings > Behavior**.

### Audio Compression

Audio is automatically optimized before upload:

- Downsampled to 16kHz mono
- Matches Gemini's internal format
- Reduces file size and upload time

## Data Management

### Audio Archival

Optionally save recordings in high-efficiency Opus format:

- ~24kbps encoding
- ~180KB per minute
- Stored in `~/.config/voice-notepad-v3/audio-archive/`

Enable in **Settings > Behavior**.

### Local Storage

All data stored locally in `~/.config/voice-notepad-v3/`:

- Configuration and API keys
- Transcript history (SQLite)
- Cost tracking data
- Audio archives (optional)

## Analysis

### Performance Metrics

Track model performance in the **Analysis** tab:

- Average inference time per model
- Characters per second output
- Total transcriptions by model
- Storage usage breakdown
