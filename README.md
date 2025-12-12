# Voice Notepad V3

A PyQt6 desktop application for voice recording with AI-powered transcription and cleanup. Uses multimodal AI models (Gemini, OpenAI GPT-4o, Mistral Voxtral) to transcribe audio AND clean it up in a single pass.

## Background

Previous voice notepad iterations used a two-phase approach: speech-to-text (ASR) followed by LLM cleanup. Voice Notepad V3 consolidates this into a single phase by leveraging multimodal AI models that accept audio as an input modality. The audio is sent directly to the model along with a cleanup prompt, and the model returns cleaned, formatted text.

This approach:
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
- **Local configuration**: Settings stored in `~/.config/voice-notepad-v3/`

## Installation

```bash
# Create virtual environment
uv venv .venv
source .venv/bin/activate

# Install dependencies
uv pip install -r requirements.txt
```

## Configuration

### API Keys

Set your API keys either:

1. **Environment variables** (or `.env` file):
   ```
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

## Project Structure

```
Voice-Notepad-V3/
├── src/                    # Source code
│   ├── main.py            # Main application
│   ├── audio_recorder.py  # Audio recording
│   ├── audio_processor.py # Audio compression
│   ├── transcription.py   # API clients
│   ├── markdown_widget.py # Markdown display
│   ├── hotkeys.py         # Global hotkey handling
│   └── config.py          # Configuration
├── planning/               # Development planning
│   ├── apiref/            # API reference docs
│   └── idea-notes/        # Original concept notes
├── scripts/                # Build scripts
│   ├── build-deb.sh       # Build .deb package
│   └── update-build.sh    # Incremental build with version bump
├── screenshots/            # Screenshots
├── requirements.txt
├── pyproject.toml
├── run.sh
└── README.md
```

## Building

### Debian Package (.deb)

Build a Debian package for distribution:

```bash
# First build
./scripts/build-deb.sh

# Incremental build (bumps patch version)
./scripts/update-build.sh

# Bump minor version and build
./scripts/update-build.sh minor

# Rebuild without version bump
./scripts/update-build.sh none
```

Build dependencies: `sudo apt install dpkg fakeroot`

Install the built package:
```bash
sudo apt install ./dist/voice-notepad_*.deb
```

## Requirements

- Python 3.10+
- PyQt6
- PyAudio (requires system audio libraries)
- ffmpeg (for audio processing via pydub)
- API keys for your chosen provider(s)

## Roadmap

Planned features for future releases:

- **Cost tracking**: Monitor API spend (today/week/month) per provider
- **Auto-copy to clipboard**: Option to automatically copy transcription to clipboard
- **Virtual input insertion**: Type transcription directly into any text field (Wayland support)
- **Debian packaging**: Build as .deb for easy Ubuntu/Debian installation

## Related Resources

- [Audio-Multimodal-AI-Resources](https://github.com/danielrosehill/Audio-Multimodal-AI-Resources) - Curated list of audio-capable multimodal AI models and APIs
- [Audio-Understanding-Test-Prompts](https://github.com/danielrosehill/Audio-Understanding-Test-Prompts) - Test prompts for evaluating audio understanding capabilities

## License

MIT
