# CLAUDE.md - Voice Notepad V3

## Project Overview

Voice Notepad V3 is a PyQt6 desktop application for voice recording with AI-powered transcription and cleanup. The key innovation is using **multimodal AI models** to transcribe audio AND clean it up in a single pass, eliminating the previous two-phase approach (ASR + LLM).

## Core Concept

Instead of separate speech-to-text followed by text cleanup, this app sends audio directly to multimodal models (via OpenRouter, Gemini, OpenAI GPT-4o, or Mistral Voxtral) along with a cleanup prompt. The model handles both transcription and text cleanup simultaneously.

## Architecture

### Directory Structure

```
Voice-Notepad-V3/
├── app/                    # Application code
│   ├── src/               # Python source files
│   └── requirements.txt   # Python dependencies
├── planning/              # Planning notes and API docs
├── scripts/
│   └── build/             # Build scripts
│       ├── deb.sh         # Build .deb package
│       ├── appimage.sh    # Build AppImage
│       ├── tarball.sh     # Build portable tarball
│       ├── all.sh         # Build all formats
│       ├── install.sh     # Install .deb from dist/
│       ├── release.sh     # Version bump + screenshots + build
│       └── screenshots.sh # Take release screenshots
├── build.sh               # Master build entry point
├── run.sh                 # Run for development
└── dist/                  # Built packages (gitignored)
```

### Source Files (in app/src/)

- `main.py` - Main PyQt6 application window and UI (tabbed interface)
- `audio_recorder.py` - Audio recording with PyAudio
- `audio_processor.py` - Audio compression and Opus archival
- `transcription.py` - API clients for OpenRouter, Gemini, OpenAI, and Mistral
- `markdown_widget.py` - Markdown rendering widget
- `config.py` - Configuration management (API keys, models, settings)
- `hotkeys.py` - Global hotkey handling using pynput
- `cost_tracker.py` - Daily API cost tracking based on token usage
- `cost_widget.py` - Cost tab for detailed spend tracking by time period
- `database.py` - SQLite database for transcription history
- `vad_processor.py` - Voice Activity Detection (silence removal) using Silero VAD
- `history_widget.py` - History tab for browsing past transcriptions
- `analysis_widget.py` - Analytics tab for model performance stats
- `models_widget.py` - Models tab showing available AI models by provider
- `about_widget.py` - About tab with app info and keyboard shortcuts
- `audio_feedback.py` - Audio beep notifications for recording start/stop

### Configuration

Settings stored in `~/.config/voice-notepad-v3/`:
- `config.json` - API keys, model selections, preferences
- `transcriptions.db` - SQLite database for transcript history
- `usage/` - Daily cost tracking JSON files
- `audio-archive/` - Opus audio archives (if enabled)
- `models/` - Downloaded VAD model (silero_vad.onnx)

### Global Hotkeys

The app supports global hotkeys that work even when the window is minimized or unfocused. Configure in Settings → Hotkeys tab.

**Shortcut Modes:**

| Mode | Description |
|------|-------------|
| **Tap to Toggle** | One key toggles recording on/off. A separate key stops and transcribes. |
| **Separate Start/Stop** | Different keys for Start, Stop (discard), and Stop & Transcribe. |
| **Push-to-Talk (PTT)** | Hold a key to record. Recording stops when you release the key. Configurable action on release (transcribe or discard). |

**Available Actions:**
- **Toggle Recording** - Start or stop recording (Tap to Toggle mode)
- **Start Recording** - Begin a new recording (Separate mode)
- **Stop & Discard** - Stop and discard the current recording (Separate mode)
- **Stop & Transcribe** - Stop recording and send to AI for transcription (all modes)
- **Push-to-Talk Key** - Hold to record, release to stop (PTT mode)

**Recommended Keys:** F14-F20 (macro keys) are suggested to avoid conflicts with other applications. These keys are available on keyboards with programmable macro keys.

**Supported Keys:**
- F1-F20 (function keys)
- Modifier combinations (Ctrl+, Alt+, Shift+, Super+)
- Media keys (on supported keyboards)

**Note:** On Wayland, global hotkeys work via XWayland compatibility layer.

### Supported AI Providers

| Provider | Models | API Endpoint |
|----------|--------|--------------|
| **OpenRouter** (Default) | `google/gemini-2.5-flash`, `google/gemini-2.5-flash-lite`, `google/gemini-2.0-flash-001`, `openai/gpt-4o-audio-preview`, `mistralai/voxtral-small-24b-2507` | OpenRouter |
| Gemini | `gemini-flash-latest`*, `gemini-2.5-flash`, `gemini-2.5-flash-lite`, `gemini-2.5-pro` | Google AI |
| OpenAI | `gpt-4o-audio-preview`, `gpt-4o-mini-audio-preview`, `gpt-audio`, `gpt-audio-mini` | OpenAI |
| Mistral | `voxtral-small-latest`, `voxtral-mini-latest` | Mistral AI |

**OpenRouter** is the recommended provider - it provides access to multiple models through a single API key, making it easy to switch between Gemini, GPT-4o, and Voxtral models.

*`gemini-flash-latest` is a dynamic endpoint that always points to Google's latest Flash model.

## Development Guidelines

### Running the App

```bash
./run.sh
```
This creates the venv in `app/.venv` if needed and launches the app.

### Environment Variables

Required in `.env` or system environment (only need the key for your chosen provider):
```
OPENROUTER_API_KEY=your_key  # Recommended - access multiple models
GEMINI_API_KEY=your_key
OPENAI_API_KEY=your_key
MISTRAL_API_KEY=your_key
```

### The Cleanup Prompt

The cleanup prompt is fully customizable via checkboxes in Settings → Prompt. Default options include:
1. Remove filler words (um, uh, like, etc.)
2. Remove verbal tics and hedging phrases (you know, I mean, etc.)
3. Remove standalone acknowledgments (Okay, Right, etc.)
4. Add proper punctuation and sentences
5. Add natural paragraph spacing
6. Follow verbal instructions in the recording (e.g., "don't include this", "change this")
7. Add subheadings for lengthy transcriptions (optional, disabled by default)
8. Use markdown formatting like bold and lists (optional, disabled by default)
9. Remove unintentional dialogue (optional, disabled by default)
   - Only removes dialogue if the AI can confidently detect it was accidental
   - E.g., someone else speaking to the user during recording

The prompt is built dynamically from selected options, along with format preset (email, todo, meeting notes, etc.), formality level (casual, neutral, professional), and verbosity reduction settings.

### Audio Processing Pipeline

Audio goes through a multi-stage pipeline before transcription:

1. **Recording** (`audio_recorder.py`)
   - Captures at device's native sample rate (typically 48kHz)
   - Automatic sample rate negotiation with device
   - Error handling for microphone disconnection during recording

2. **Automatic Gain Control (AGC)** (`audio_processor.py`)
   - Normalizes audio levels for consistent transcription accuracy
   - Target peak: -3 dBFS (leaves headroom while ensuring good signal)
   - Minimum threshold: -40 dBFS (avoids amplifying noise in silent recordings)
   - Maximum gain: +20 dB (prevents over-amplification of very quiet audio)
   - Only boosts quiet audio—never attenuates loud audio

3. **Voice Activity Detection (VAD)** (`vad_processor.py`)
   - Silero VAD removes silence segments before API upload
   - Reduces file size and API costs
   - See VAD section below for technical parameters

4. **Compression** (`audio_processor.py`)
   - Downsampled to 16kHz mono (matches Gemini's internal format)
   - Converted to WAV for API upload
   - Optional Opus archival for storage efficiency

**AGC Configuration Constants:**
```python
AGC_TARGET_PEAK_DBFS = -3.0   # Target peak level
AGC_MIN_PEAK_DBFS = -40.0     # Skip AGC if audio is quieter (noise floor)
AGC_MAX_GAIN_DB = 20.0        # Maximum boost to apply
```

## Features

### Implemented

- [x] **Global hotkeys**: System-wide keyboard shortcuts (F14-F20 recommended)
- [x] **Cost tracking**: Actual costs via OpenRouter API, estimates for other providers
- [x] **OpenRouter balance**: Live credit balance in status bar and Cost tab
- [x] **Transcript history**: SQLite database stores all transcriptions with metadata
- [x] **VAD (Voice Activity Detection)**: Strips silence before API upload (reduces cost)
- [x] **Automatic Gain Control (AGC)**: Normalizes audio levels for consistent transcription accuracy
- [x] **Audio archival**: Optional Opus archival (~24kbps, very small files)
- [x] **History tab**: Browse, search, and reuse past transcriptions
- [x] **Cost tab**: Balance, spending (hourly/daily/weekly/monthly), model breakdown
- [x] **Analysis tab**: Model performance metrics (inference time, chars/sec)
- [x] **Models tab**: Browse available models by provider with tier indicators
- [x] **Tabbed interface**: Record, History, Cost, Analysis, Models, and About tabs
- [x] **Append mode**: Record multiple clips and combine them before transcription

### Planned

- [ ] **Auto-copy to clipboard**: Automatic clipboard copy after transcription
- [ ] **Virtual input insertion**: Type transcription into any text field (Wayland challenge)
- [x] **Debian packaging**: Build as .deb for easy distribution
- [ ] **S3 cloud backup**: Mirror local data to object storage
- [ ] **Words per minute tracking**: Analyze speech patterns

## Building & Packaging

All build operations are accessed through a single master script: `./build.sh`

### Quick Reference

| Command | Purpose |
|---------|---------|
| `./build.sh` | Show help and available commands |
| `./build.sh --deb` | Build Debian package |
| `./build.sh --appimage` | Build AppImage |
| `./build.sh --tarball` | Build portable tarball |
| `./build.sh --all` | Build all formats + checksums |
| `./build.sh --install` | Install latest .deb from dist/ |
| `./build.sh --dev` | Fast dev build + install |
| `./build.sh --release` | Bump version + screenshots + build all |

### Package Builds

```bash
./build.sh --deb [VERSION]       # Build Debian package
./build.sh --appimage [VERSION]  # Build AppImage
./build.sh --tarball [VERSION]   # Build portable tarball
./build.sh --all [VERSION]       # Build all formats + checksums
```

Output files:
- `dist/voice-notepad_VERSION_amd64.deb` - Debian/Ubuntu package
- `dist/Voice_Notepad-VERSION-x86_64.AppImage` - Universal Linux
- `dist/voice-notepad-VERSION-linux-x86_64.tar.gz` - Portable archive
- `dist/voice-notepad-VERSION-SHA256SUMS.txt` - Checksums

### Development Workflow

```bash
./build.sh --dev              # Fast build + install (skips compression)
./build.sh --deb --fast       # Build .deb without compression
./build.sh --install          # Install latest .deb from dist/
```

### Release Workflow

```bash
./build.sh --release              # Patch release (1.3.0 -> 1.3.1)
./build.sh --release minor        # Minor release (1.3.0 -> 1.4.0)
./build.sh --release major        # Major release (1.3.0 -> 2.0.0)
./build.sh --release-deb          # Patch release, .deb only
./build.sh --screenshots          # Take screenshots only
```

Release workflow:
1. Bumps version in `pyproject.toml`
2. Takes screenshots
3. Builds packages (all formats, or deb-only with `--release-deb`)

### Build Script Details

Individual build scripts are located in `scripts/build/`:
- `deb.sh` - Debian package with venv caching
- `appimage.sh` - AppImage (downloads appimagetool automatically)
- `tarball.sh` - Portable tarball with install/uninstall scripts
- `all.sh` - Orchestrates all builds + checksums
- `install.sh` - Installs .deb (requires sudo)
- `release.sh` - Version bump + screenshots + build
- `screenshots.sh` - Take UI screenshots

### Package Details

**All formats include:**
- Bundled Python venv with all dependencies
- Launcher script with Wayland support
- Desktop entry and icon

**System dependencies:**
- python3, python3-venv, ffmpeg, portaudio19-dev

### CI/CD (GitHub Actions)

Releases are built automatically in the cloud via GitHub Actions.

**Trigger a release:**
```bash
git tag v1.0.0
git push origin v1.0.0
```

Or manually via GitHub Actions → "Build Release" → "Run workflow"

**What gets built:**
- Linux: .deb, AppImage, tarball (Ubuntu runner)
- Windows: .zip with PyInstaller bundle (Windows runner)
- SHA256 checksums
- GitHub Release with all artifacts attached

The workflow is defined in `.github/workflows/release.yml`.

## Cost Tracking

The app tracks API costs with **OpenRouter providing actual key-specific costs** from the API. Other providers use token-based estimates only.

### OpenRouter (Recommended)
OpenRouter provides the most accurate cost tracking:
- **Key-specific usage**: Uses `/api/v1/key` endpoint to get usage for your specific API key (not account-wide)
- **Account balance**: Displayed in status bar and Cost tab via `/api/v1/credits`
- **Activity breakdown**: Model usage breakdown via `/api/v1/activity` endpoint (last 30 days)

### Status Bar Display
- Shows "Today: $X.XXXX (N) | Bal: $X.XX" when using OpenRouter
- N = number of transcriptions today (from local database)
- Bal = remaining OpenRouter credit balance

### Cost Tab Features
- **OpenRouter Balance**: Live account balance (cached 60 seconds)
- **API Key Usage**: Daily, weekly, monthly spend for the configured key only
- **Model Breakdown**: Usage by model from OpenRouter's activity API
- **Local Statistics**: Transcription count, words, and characters from local database

### Source Files
- `openrouter_api.py` - OpenRouter API client for credits, key info, and activity
- `cost_widget.py` - Cost tab UI with balance, key usage, and model breakdown
- `cost_tracker.py` - Legacy token-based cost estimation (non-OpenRouter)

### Database Fields for Cost Analysis
The database tracks per-transcription metrics:
- `input_tokens` / `output_tokens` - Token counts
- `estimated_cost` - Actual cost (OpenRouter) or estimated (others)
- `audio_duration_seconds` / `vad_audio_duration_seconds` - Audio length
- `text_length` / `word_count` - Output transcript metrics
- `prompt_text_length` - System prompt length sent to API

**Note:** Only OpenRouter provides accurate key-specific cost data. Other providers show estimates based on token pricing which may not reflect actual billing.

## Voice Activity Detection (VAD)

VAD is enabled by default (Settings → Behavior → Enable VAD). It uses [Silero VAD](https://github.com/snakers4/silero-vad) (ONNX model) to detect speech segments and remove silence before sending audio to the API.

**Benefits:**
- Reduces audio file size by removing silence
- Lowers API costs (fewer audio tokens)
- Faster upload times

**Model:**
- **Silero VAD** - lightweight ONNX model (~1.4MB)
- Downloaded automatically on first use to `~/.config/voice-notepad-v3/models/silero_vad.onnx`
- GitHub: https://github.com/snakers4/silero-vad

**Technical parameters:**
- Sample rate: 16kHz
- Window size: 512 samples (~32ms)
- Speech probability threshold: 0.5
- Minimum speech segment: 250ms
- Speech padding: 30ms

## Transcript History

All transcriptions are automatically saved to a local SQLite database with:
- Timestamp
- Provider and model used
- Transcript text
- Audio duration (original and after VAD)
- Inference time in milliseconds
- Token usage and estimated cost
- Optional archived audio file path

**History Tab:**
- Search transcriptions by text content
- Click to preview, double-click to load into editor
- View metadata (duration, inference time, cost)
- Delete individual transcriptions

**Analysis Tab:**
- Summary stats for last 7 days
- Model performance comparison (avg inference time, chars/sec)
- Total storage usage breakdown

## Audio Archival

Optional feature (Settings → Behavior → Archive audio recordings). When enabled, audio is saved in Opus format (~24kbps) to `~/.config/voice-notepad-v3/audio-archive/`.

**Format:** Opus codec optimized for speech. A 1-minute recording uses ~180KB.

## Testing Changes

When modifying transcription providers:
1. Test with short recordings (~10-30 seconds)
2. Verify cleanup prompt is being applied
3. Check markdown formatting in output
4. Confirm audio compression is working

## Related Resources

- `planning/idea-notes/` - Original concept recordings and transcripts
- `planning/apiref/` - API documentation for providers
