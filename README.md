# Voice Notepad
![alt text](screenshots/v1/image.png)

Notepad app that offers a variety of multimodal audio models for single operation transcription and light text cleanup (as opposed to ASR + LLM combination).

Supported backends:

- **OpenRouter** (recommended): Access multiple models (Gemini, GPT-4o, Voxtral) through a single API key with accurate cost tracking
- **Gemini**: Direct Google AI access, `flash-latest` is default preset
- **OpenAI**: Direct OpenAI access for GPT-4o audio models
- **Mistral/Voxtral**: Direct Mistral access for Voxtral models

## Scope

This app focuses specifically on **audio multimodal models**—AI models that can directly process audio input for transcription. This is distinct from traditional ASR (automatic speech recognition) pipelines that require a separate LLM pass for text cleanup.

**What this app is:**
- A simple interface for single-pass transcription + basic cleanup
- Focused on the small but growing category of audio-capable multimodal models
- A lightweight tool with a standard cleanup prompt (remove filler words, add punctuation, follow verbal instructions)

**What this app is not:**
- A platform for elaborate text formatting or custom prompt engineering
- A general-purpose transcription tool using traditional ASR
- An "omnimodel" showcase (the focus is specifically on audio→text, not broader multimodal capabilities)

The list of supported models is intentionally curated to those that genuinely support audio multimodal transcription. If you're an API provider rolling out audio multimodal capabilities, feel free to open an issue or PR.

## How It Works

Voice Notepad sends your audio recording directly to multimodal AI models along with a cleanup prompt. The model handles both transcription and text cleanup simultaneously, returning polished, formatted text.

This single-pass approach:
- Reduces latency (one API call instead of two)
- Produces more contextually aware cleanup (the model "hears" the original audio)
- Supports verbal instructions embedded in the recording (e.g., "delete that last part")

## Features

- **One-shot transcription + cleanup**: Audio is sent with a cleanup prompt to multimodal models, eliminating the need for separate ASR and LLM passes
- **Multiple AI providers**: Gemini, OpenAI, and Mistral (Voxtral)
- **Audio compression**: Automatic downsampling to 16kHz mono before upload (reduces file size, matches Gemini's internal format)
- **Markdown rendering**: Transcriptions display with rendered markdown formatting (toggle to view/edit source)
- **System tray integration**: Minimizes to tray for quick access
- **Microphone selection**: Choose your preferred input device
- **Recording controls**: Record, pause, resume, stop, delete
- **Save & copy**: Save to markdown files or copy to clipboard
- **Word count**: Live word and character count
- **Keyboard shortcuts**: Full keyboard control for efficient workflow
- **Global hotkeys**: System-wide hotkeys work even when app is minimized (F14-F20 recommended)
- **Cost tracking**: Monitor API spend (today/week/month) with accurate key-specific usage for OpenRouter
- **Transcript history**: SQLite database stores all transcriptions with metadata
- **VAD (Voice Activity Detection)**: Optional silence removal before API upload (reduces cost)
- **Audio archival**: Optional Opus archival of recordings
- **Local configuration**: Settings stored in `~/.config/voice-notepad-v3/`

## Installation

### Quick Start

```bash
# Clone the repository
git clone https://github.com/danielrosehill/Voice-Notepad.git
cd Voice-Notepad

# Run the app
./run.sh
```

The `run.sh` script automatically creates a virtual environment and installs dependencies.

### From Source (Manual)

```bash
cd app

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run
python -m src.main
```

### System Dependencies

```bash
# Ubuntu/Debian
sudo apt install python3 python3-venv ffmpeg portaudio19-dev
```

## Configuration

### API Keys

Set your API keys either:

1. **Environment variables** (or `.env` file):
   ```
   OPENROUTER_API_KEY=your_key  # Recommended - access multiple models
   GEMINI_API_KEY=your_key
   OPENAI_API_KEY=your_key
   MISTRAL_API_KEY=your_key
   ```

2. **Settings dialog**: Click "Settings" in the app to configure API keys

### Models

Default models:
- **Gemini**: `gemini-2.0-flash-lite`
- **OpenAI**: `gpt-4o-audio-preview`
- **Mistral**: `voxtral-mini-latest`

These can be changed in Settings > Models.

## Usage

```bash
./run.sh
# or
source .venv/bin/activate
python -m src.main
```

1. Select your microphone and AI provider
2. Click **Record** to start recording (or press `Ctrl+R`)
3. Click **Stop & Transcribe** when done (or press `Ctrl+Return`)
4. The cleaned transcription appears with markdown formatting
5. Click **Save** to export or **Copy** to clipboard

### Keyboard Shortcuts (In-App)

| Shortcut | Action |
|----------|--------|
| `Ctrl+R` | Start recording |
| `Ctrl+Space` | Pause/Resume recording |
| `Ctrl+Return` | Stop and transcribe |
| `Ctrl+S` | Save to file |
| `Ctrl+Shift+C` | Copy to clipboard |
| `Ctrl+N` | New note |

### Global Hotkeys

Global hotkeys work even when the app is minimized or unfocused. Configure them in **Settings > Hotkeys**.

**Recommended keys**: F14-F16 (macro keys) to avoid conflicts with other applications.

| Default | Action |
|---------|--------|
| F14 | Start recording |
| F15 | Stop recording (discard) |
| F16 | Stop & transcribe |

Supports: F1-F20, modifier combinations (Ctrl+, Alt+, Shift+, Super+), and media keys.

### System Tray

- Closing the window minimizes to system tray
- Click the tray icon to show/hide the window
- Right-click for quick actions (Show, Start Recording, Quit)

## Cleanup Prompt

The default cleanup prompt instructs the AI to:
- Remove filler words (um, uh, like, etc.)
- Add proper punctuation and sentences
- Add natural paragraph spacing
- Follow verbal instructions in the recording
- Add subheadings for lengthy transcriptions
- Return output as markdown

Customize the prompt in Settings > Prompt.

## Cost Tracking

The Cost tab provides detailed API usage tracking. **OpenRouter is recommended** for accurate cost tracking because it provides:

- **Key-specific usage**: Daily, weekly, and monthly spend for your configured API key only (not account-wide)
- **Model breakdown**: See which models are costing the most (last 30 days from OpenRouter's activity API)
- **Account balance**: Real-time credit balance display

**Note**: Only OpenRouter provides accurate cost data via its API. Other providers (Gemini, OpenAI, Mistral) show estimated costs based on token counts, which may not reflect actual billing.

## Project Structure

```
Voice-Notepad/
├── app/
│   ├── src/               # Python source code
│   │   ├── main.py        # Main application
│   │   ├── audio_recorder.py
│   │   ├── transcription.py
│   │   └── ...
│   └── requirements.txt
├── docs/                  # Documentation (MkDocs)
├── screenshots/
├── build.sh               # Build .deb package
├── install.sh             # Install from .deb
├── run.sh                 # Run for development
├── mkdocs.yml             # Documentation config
└── README.md
```

## Building

### Debian Package (.deb)

Build a Debian package for distribution:

```bash
# Build the package
./build.sh

# Install the package
./install.sh

# Or build and install in one step
./build-install.sh
```

Build dependencies: `sudo apt install dpkg fakeroot`

### Documentation Site

Build and serve the documentation locally:

```bash
# Install MkDocs with Material theme
pip install mkdocs-material

# Serve locally
mkdocs serve

# Build static site
mkdocs build
```

## Requirements

- Python 3.10+
- PyQt6
- PyAudio (requires system audio libraries)
- ffmpeg (for audio processing via pydub)
- API keys for your chosen provider(s)

## Roadmap

Planned features for future releases:

- **Virtual input insertion**: Type transcription directly into any text field (Wayland support)
- **S3 cloud backup**: Mirror local data to object storage
- **Words per minute tracking**: Analyze speech patterns

## Related Resources

- [Audio-Multimodal-AI-Resources](https://github.com/danielrosehill/Audio-Multimodal-AI-Resources) - Curated list of audio-capable multimodal AI models and APIs
- [Audio-Understanding-Test-Prompts](https://github.com/danielrosehill/Audio-Understanding-Test-Prompts) - Test prompts for evaluating audio understanding capabilities

## License

MIT
