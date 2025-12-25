# Technology Stack

## Core Components

**PyQt6** provides the desktop GUI with a tabbed interface, system tray integration, and keyboard shortcuts.

**PyAudio** handles microphone recording. **pydub** processes audio format conversion. **Silero VAD** runs through **onnxruntime** for voice activity detection.

**SQLite** stores transcript history. **JSON** stores configuration and daily cost tracking. **Opus** codec archives recordings.

## AI Provider SDKs

| Provider | SDK |
|----------|-----|
| OpenRouter | openai (compatible) |
| Google | google-genai |
| OpenAI | openai |
| Mistral | mistralai |

OpenRouter uses the OpenAI SDK with a custom base URL.

## Python Dependencies

```
PyQt6>=6.6.0
pyaudio>=0.2.14
pydub>=0.25.1
audioop-lts>=0.2.0
google-genai>=1.0.0
openai>=1.40.0
mistralai>=1.0.0
onnxruntime>=1.16.0
markdown>=3.5.0
pynput>=1.7.6
httpx>=0.27.0
```

## System Dependencies

Install on Ubuntu/Debian:

```bash
sudo apt install python3 python3-venv ffmpeg portaudio19-dev
```

## External Services

| Service | Endpoint |
|---------|----------|
| OpenRouter | openrouter.ai/api/v1 |
| Google AI | generativelanguage.googleapis.com |
| OpenAI | api.openai.com/v1 |
| Mistral | api.mistral.ai/v1 |

The Silero VAD model (~1.4MB) is downloaded automatically on first use to `~/.config/voice-notepad-v3/models/`.

## File Locations

```
~/.config/voice-notepad-v3/
├── config.json
├── transcriptions.db
├── usage/
├── audio-archive/
└── models/
    └── silero_vad.onnx
```
