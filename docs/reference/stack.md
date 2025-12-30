# Technology Stack

## Overview

AI Transcription Notepad combines several key technologies to deliver single-pass voice transcription with AI cleanup.

## Core Components

| Component | Technology | Purpose |
|-----------|------------|---------|
| **UI Framework** | PyQt6 | Desktop GUI with tabbed interface, system tray, keyboard shortcuts |
| **Audio Recording** | PyAudio | Microphone capture with device selection |
| **Audio Processing** | pydub + FFmpeg | Format conversion, compression, gain control |
| **Voice Activity Detection** | [TEN VAD](https://github.com/TEN-framework/ten-vad) | Removes silence before API upload to reduce costs |
| **Text-to-Speech** | [Microsoft Edge TTS](https://github.com/rany2/edge-tts) | Audio feedback announcements |
| **Database** | [Mongita](https://github.com/scottrogowski/mongita) | MongoDB-compatible local storage for transcripts |
| **Charts** | pyqtgraph | Analytics visualizations |
| **Global Hotkeys** | pynput + evdev | System-wide keyboard shortcuts |

## Transcription Backends

The app sends audio directly to multimodal AI models for single-pass transcription and cleanup.

| Provider | SDK | Endpoint | Notes |
|----------|-----|----------|-------|
| **Google Gemini** (recommended) | google-genai | generativelanguage.googleapis.com | Supports `gemini-flash-latest` dynamic endpoint |
| **OpenRouter** | openai (compatible) | openrouter.ai/api/v1 | Accurate per-key cost tracking |

## Voice Activity Detection

**TEN VAD** is a lightweight native library (~306KB) that detects speech segments and removes silence before sending audio to the API. This reduces file size and API costs.

- Bundled with the `ten-vad` pip package (no download required)
- Sample rate: 16kHz
- Faster and more accurate than Silero VAD for real-time use
- Requires `libc++1` on Linux: `sudo apt install libc++1`

## Text-to-Speech

**Microsoft Edge TTS** powers the voice announcements in TTS audio feedback mode.

- Voice: British English male (en-GB-RyanNeural)
- Pre-generated audio files bundled in `app/assets/tts/` (~1.7MB)
- Dynamic generation available for analytics readout
- Uses `edge-tts` Python package

## Python Dependencies

```
PyQt6>=6.6.0          # Desktop GUI framework
pyaudio>=0.2.14       # Audio recording
google-genai>=1.0.0   # Gemini API client
openai>=1.40.0        # OpenRouter API (OpenAI-compatible)
pydub>=0.25.1         # Audio processing
ten-vad>=1.0.6        # Voice activity detection
edge-tts>=6.1.0       # Text-to-speech for announcements
mongita>=1.2.0        # MongoDB-compatible local database
markdown>=3.5.0       # Markdown rendering
pynput>=1.7.6         # Keyboard input handling
evdev>=1.6.0          # Linux input device access (hotkeys)
httpx>=0.27.0         # HTTP client
pyqtgraph>=0.13.0     # Charts and visualizations
```

## System Dependencies

Install on Ubuntu/Debian:

```bash
sudo apt install python3 python3-venv ffmpeg portaudio19-dev libc++1
```

Or run the dependency checker:

```bash
./scripts/install-deps.sh
```

## File Locations

```
~/.config/voice-notepad-v3/
├── config.json           # Settings and API keys
├── mongita/              # MongoDB-compatible database
├── usage/                # Daily cost tracking (JSON)
└── audio-archive/        # Opus recordings (if enabled)
```

## Audio Archival

When enabled, recordings are saved in **Opus** format optimized for speech:
- Bitrate: ~24kbps
- A 1-minute recording uses ~180KB
- Stored in `~/.config/voice-notepad-v3/audio-archive/`
