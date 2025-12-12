# CLAUDE.md - Voice Notepad V3

## Project Overview

Voice Notepad V3 is a PyQt6 desktop application for voice recording with AI-powered transcription and cleanup. The key innovation is using **multimodal AI models** to transcribe audio AND clean it up in a single pass, eliminating the previous two-phase approach (ASR + LLM).

## Core Concept

Instead of separate speech-to-text followed by text cleanup, this app sends audio directly to multimodal models (Gemini, OpenAI GPT-4o, Mistral Voxtral) along with a cleanup prompt. The model handles both transcription and text cleanup simultaneously.

## Architecture

### Source Files

- `src/main.py` - Main PyQt6 application window and UI
- `src/audio_recorder.py` - Audio recording with PyAudio
- `src/audio_processor.py` - Audio compression (downsample to 16kHz mono)
- `src/transcription.py` - API clients for Gemini, OpenAI, and Mistral
- `src/markdown_widget.py` - Markdown rendering widget
- `src/config.py` - Configuration management (API keys, models, settings)
- `src/hotkeys.py` - Global hotkey handling using pynput

### Configuration

Settings stored in `~/.config/voice-notepad-v3/`:
- API keys (Gemini, OpenAI, Mistral)
- Model selections
- Cleanup prompt customization
- UI preferences
- Global hotkey bindings

### Global Hotkeys

The app supports global hotkeys that work even when the window is minimized or unfocused. Configure in Settings → Hotkeys tab.

**Available Actions:**
- **Start Recording** - Begin a new recording
- **Stop Recording (discard)** - Stop and discard the current recording
- **Stop & Transcribe** - Stop recording and send to AI for transcription

**Recommended Keys:** F14-F20 (macro keys) are suggested to avoid conflicts with other applications. These keys are available on keyboards with programmable macro keys.

**Supported Keys:**
- F1-F20 (function keys)
- Modifier combinations (Ctrl+, Alt+, Shift+, Super+)
- Media keys (on supported keyboards)

**Note:** On Wayland, global hotkeys work via XWayland compatibility layer.

### Supported AI Providers

| Provider | Model | API Endpoint |
|----------|-------|--------------|
| Gemini | `gemini-2.0-flash-lite` (default) | Google AI |
| OpenAI | `gpt-4o-audio-preview` | OpenAI |
| Mistral | `voxtral-mini-latest` | Mistral AI |

## Development Guidelines

### Running the App

```bash
source .venv/bin/activate
python -m src.main
# or
./run.sh
```

### Environment Variables

Required in `.env` or system environment:
```
GEMINI_API_KEY=your_key
OPENAI_API_KEY=your_key
MISTRAL_API_KEY=your_key
```

### The Cleanup Prompt

The default cleanup prompt instructs the AI to:
1. Remove filler words (um, uh, like, etc.)
2. Add proper punctuation and sentences
3. Add natural paragraph spacing
4. Follow verbal instructions in the recording (e.g., "don't include this", "change this")
5. Add subheadings for lengthy transcriptions
6. Return output as markdown

### Audio Processing

Audio is compressed before upload:
- Downsampled to 16kHz mono (matches Gemini's internal format)
- Converted to appropriate format for each provider
- Reduces file size and upload time

## Planned Features

From the original concept notes:

- [x] **Global hotkeys**: System-wide keyboard shortcuts (F14-F20 recommended)
- [ ] **Cost tracking**: Track API spend (today/week/month)
- [ ] **Auto-copy to clipboard**: Automatic clipboard copy after transcription
- [ ] **Virtual input insertion**: Type transcription into any text field (Wayland challenge)
- [ ] **Debian packaging**: Build as .deb for easy distribution

## Testing Changes

When modifying transcription providers:
1. Test with short recordings (~10-30 seconds)
2. Verify cleanup prompt is being applied
3. Check markdown formatting in output
4. Confirm audio compression is working

## Related Resources

- `planning/idea-notes/` - Original concept recordings and transcripts
- `planning/apiref/` - API documentation for providers
