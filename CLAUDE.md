# CLAUDE.md - AI Transcription Notepad V3

## Project Overview

AI Transcription Notepad V3 is a PyQt6 desktop application for voice recording with AI-powered transcription and cleanup. The key innovation is using **multimodal AI models** to transcribe audio AND clean it up in a single pass, eliminating the previous two-phase approach (ASR + LLM).

## Core Concept

Instead of separate speech-to-text followed by text cleanup, this app sends audio directly to Google's Gemini multimodal models along with a cleanup prompt. The model handles both transcription and text cleanup simultaneously.

**Why Gemini?** After extensive testing (~1000 transcriptions), Gemini Flash models have proven highly cost-effective for voice transcription—typically just a few dollars for heavy usage. The recommended `gemini-flash-latest` endpoint automatically points to Google's latest Flash model, eliminating manual updates.

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
- `transcription.py` - API clients for Gemini (direct) and OpenRouter
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

The app supports global hotkeys that work system-wide, even when the window is minimized or unfocused.

**FIXED F-KEY MAPPING (Current Implementation):**

| Key | Action | Description |
|-----|--------|-------------|
| **F15** | Simple Toggle | Start recording, or stop and **transcribe immediately**. |
| **F16** | Tap Toggle | Start recording, or stop and cache audio (for append mode). |
| **F17** | Transcribe Only | Transcribe cached audio without starting a new recording. If currently recording, stops and transcribes. |
| **F18** | Clear/Delete | Delete current recording and clear all cached audio. |
| **F19** | Append | Start a new recording that will be appended to the cached audio. |

**Simple Workflow (F15 only):**
1. Press **F15** to start recording
2. Press **F15** again to stop and transcribe

**Append Workflow (F16/F17/F19):**
1. Press **F16** to start recording
2. Press **F16** again to stop and cache (audio is held in memory)
3. Press **F19** to record another segment (appends to cache)
4. Press **F17** to transcribe all cached segments together
5. Press **F18** to clear cache and start over

**Note:** The Settings → Hotkeys tab UI is currently disabled. The F15-F19 mapping is hardcoded for simplicity and will be made configurable in a future release.

**Technical Details:**
- Hotkeys work system-wide (even when app is minimized or unfocused)
- On Wayland, hotkeys work via evdev (reads directly from input-remapper devices)
- Requires user to be in the 'input' group for evdev access
- Falls back to pynput/X11 on non-Linux systems
- Compatible with keyboards that have macro/function keys beyond F12

### Supported AI Providers

| Provider | Models | API Endpoint |
|----------|--------|--------------|
| **Gemini Direct** (Recommended) | `gemini-flash-latest`*, `gemini-2.5-flash`, `gemini-2.5-flash-lite`, `gemini-2.5-pro` | Google AI |
| OpenRouter | `google/gemini-2.5-flash`, `google/gemini-2.5-flash-lite`, `google/gemini-2.0-flash-001` | OpenRouter |

**Gemini Direct** is the recommended provider because it supports the dynamic `gemini-flash-latest` endpoint, which always points to Google's latest Flash model automatically. This eliminates the need for manual model updates.

*`gemini-flash-latest` is only available through the direct Gemini API, not through OpenRouter.

## Development Guidelines

### Running the App

```bash
./run.sh
```
This creates the venv in `app/.venv` if needed and launches the app.

### Environment Variables

Required in `.env` or system environment (only need the key for your chosen provider):
```
GEMINI_API_KEY=your_key      # Recommended - supports gemini-flash-latest
OPENROUTER_API_KEY=your_key  # Alternative - access via OpenAI-compatible API
```

### The Cleanup Prompt

AI Transcription Notepad uses a layered prompt system to transform speech into clean, well-formatted text. This is single-pass dictation processing: audio in, edited text out.

#### Short Audio Optimization

For recordings under 30 seconds, a minimal prompt is used instead of the full layered system. This reduces API overhead for quick notes while still applying essential cleanup:
- Add punctuation (periods, commas, question marks)
- Capitalize sentences properly
- Remove filler words (um, uh, like, you know)
- Fix obvious grammar errors
- Break into paragraphs if multiple distinct thoughts

This is a backend optimization—no UI changes or user action required. The threshold is defined by `SHORT_AUDIO_THRESHOLD_SECONDS` (30.0) in `config.py`.

**Prompt size comparison:**
- Full prompt: ~4,300 characters
- Short audio prompt: ~300 characters

#### Foundation Cleanup (Always Applied)

The foundation layer is always applied to every transcription. This is what distinguishes AI Transcription Notepad from traditional speech-to-text. Defined in `config.py` as `FOUNDATION_PROMPT_SECTIONS`.

**1. Task Definition**
- Transform audio into polished, publication-ready text—not a verbatim transcript
- Apply intelligent editing, removing artifacts of natural speech while preserving intended meaning
- Output only the transformed text, no preamble or commentary

**2. User Details**
- User's name (Daniel) is used for signatures where appropriate (e.g., emails)
- Additional personalization elements (email, signature) are injected into templates

**3. Background Audio**
- Exclude audio not intended for transcription: greetings to others, side conversations, delivery interruptions, background noise
- Include only content representing the user's intended message

**4. Filler Words**
- Remove filler words and verbal hesitations: "um", "uh", "er", "like", "you know", "I mean", "basically", "actually", "sort of", "kind of", "well" (at sentence beginnings)
- Preserve these words only when they carry semantic meaning

**5. Repetitions**
- Remove redundant repetitions where the same thought is expressed multiple times
- Consolidate repeated concepts into a single, clear expression

**6. Meta Instructions**
- Honor verbal directives like "scratch that", "don't include that", "ignore what I just said"
- Remove the meta-instructions themselves from the output

**7. Spelling Clarifications**
- When user spells out a word ("Zod is spelled Z-O-D"), use correct spelling but omit the instruction
- Handles infrequently encountered words and technical terms

**8. Grammar & Typos**
- Correct spelling errors, typos, and grammatical mistakes
- Fix subject-verb agreement, tense consistency, proper word usage
- Fix homophones (their/there/they're, your/you're)
- Correct minor speech grammar errors (e.g., "into the option" → "into the options")

**9. Punctuation**
- Add periods, commas, colons, semicolons, question marks, quotation marks
- Break text into logical paragraphs based on topic shifts
- Ensure proper capitalization

**10. Format Detection**
- Infer intended format (email, to-do list, meeting notes) and format accordingly
- Match tone to context: professional for business, informal for casual

**11. Clarity**
- Tighten rambling sentences without removing information
- Clarify confusing phrasing while preserving meaning

#### Optional Enhancements (Checkboxes)

Additional options available in Settings → Prompt:
- Add subheadings for long transcriptions
- Use markdown formatting (bold, lists, etc.)
- Remove unintentional dialogue (if the AI can confidently detect it was accidental)
- Enhance AI prompts for effectiveness (only applies to prompt-format outputs)

#### Format Presets

The prompt is further customized by:
- **Format preset**: email, todo, meeting notes, AI prompt, dev prompt, tech docs, etc.
- **Formality level**: casual, neutral, professional
- **Verbosity reduction**: none, minimum, short, medium, maximum

### Email Personalization

AI Transcription Notepad supports **multiple email addresses and signatures** for different contexts via Settings → Personalization:

- **Business Email**: Professional email address and signature for work communications
- **Personal Email**: Personal email address and signature for casual communications
- **User Name**: Your name (used in both business and personal contexts)

When generating content with the "Email" format preset, the app automatically injects the appropriate signature using **prompt injection**. The system prioritizes business email/signature by default, then falls back to personal email/signature if business fields are empty.

**How it works:**
1. Configure your business and/or personal email settings in Settings → Personalization
2. Select "Email" as the format preset when transcribing
3. The AI model receives the signature information via system prompt
4. Generated emails automatically include your configured signature

This feature eliminates the need to manually add signatures to dictated emails, and ensures consistent professional formatting across all email transcriptions.

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
- [x] **Transcript history**: MongoDB-compatible database (Mongita) stores all transcriptions with metadata
- [x] **VAD (Voice Activity Detection)**: Strips silence before API upload (reduces cost)
- [x] **Automatic Gain Control (AGC)**: Normalizes audio levels for consistent transcription accuracy
- [x] **Audio archival**: Optional Opus archival (~24kbps, very small files)
- [x] **History tab**: Browse, search, and reuse past transcriptions
- [x] **Cost tab**: Balance, spending (hourly/daily/weekly/monthly), model breakdown
- [x] **Analysis tab**: Model performance metrics (inference time, chars/sec)
- [x] **Models tab**: Browse available models by provider with tier indicators
- [x] **Tabbed interface**: Record, History, Cost, Analysis, Models, Prompt Stacks, and About tabs
- [x] **Append mode**: Record multiple clips and combine them before transcription
- [x] **Prompt Stacks**: Layered prompt system for complex workflows (meeting notes + action items, technical docs, etc.)
- [x] **Dev mode indicator**: Development version shows "(DEV)" in window title for visual distinction
- [x] **Short audio optimization**: Minimal prompt for recordings < 30s (reduces API overhead by ~93%)

### Planned

- [x] **Combinable output modes**: App, Clipboard, and Inject can be enabled in any combination (all three, any two, or just one)
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

## Database Architecture

AI Transcription Notepad uses **Mongita**, a pure Python implementation of MongoDB, for local data storage. This provides a document-based database that's more flexible than traditional SQL databases.

### Why MongoDB/Mongita?

- **Document Storage**: Natural fit for storing transcriptions with nested metadata
- **Schema Flexibility**: Easy to add new fields without migrations
- **Pure Python**: No external database server required (all data stored locally)
- **MongoDB Compatible**: Uses standard MongoDB query syntax
- **Full-Text Search**: Built-in text search capabilities

### Database Location

All data is stored locally at `~/.config/voice-notepad-v3/mongita/`

### Collections

- **`transcriptions`**: Stores all transcript records with metadata (provider, model, tokens, cost, etc.)
- **`prompt_stacks`**: Stores saved prompt combinations for reuse

### Source Files

- `database_mongo.py` - MongoDB database interface (replaces old `database.py`)
- Legacy SQLite data is automatically migrated on first run

### Document Structure

Each transcription document contains:
```python
{
    "timestamp": str,
    "provider": str,
    "model": str,
    "transcript_text": str,
    "audio_duration_seconds": float,
    "inference_time_ms": int,
    "input_tokens": int,
    "output_tokens": int,
    "estimated_cost": float,
    "text_length": int,
    "word_count": int,
    "audio_file_path": str (optional),
    "vad_audio_duration_seconds": float (optional),
    "prompt_text_length": int,
    "source": str ("recording" or "file"),
    "source_path": str (optional)
}
```

## Prompt Stacks

Prompt Stacks allow you to layer multiple AI instructions for complex transcription scenarios. Each stack is a collection of prompts that get combined with the base cleanup prompt.

### Use Cases

- **Meeting Notes + Action Items**: Transcribe and automatically extract action items
- **Technical Documentation + Code**: Extract code snippets while formatting as markdown
- **Multi-Language**: Transcribe and translate simultaneously
- **Custom Workflows**: Build specialized prompts for recurring tasks

### Features

- Create and save named prompt stacks
- Combine multiple prompts that stack together
- Import/export as JSON for sharing
- Apply to any transcription (recording or file upload)

### Source Files

- `prompt_stack_widget.py` - Prompt Stacks tab UI
- `prompt_elements.py` - Prompt building utilities

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

## FAQ

### When are UI parameters applied?

**All UI parameters are captured at transcription time, not recording time.**

This means you can:
- Start recording
- Change your mind about the format preset (email → todo list)
- Change the model (gemini-flash-latest → gemini-2.5-pro)
- Adjust formality level or verbosity
- Modify prompt checkboxes

When you click **Transcribe**, the app uses whatever settings are currently selected in the UI at that moment. This gives you flexibility to adjust parameters between recording and transcription.

**UI parameters that are applied at transcription:**
- Format preset (email, todo, meeting notes, etc.)
- Model selection (provider and specific model)
- Formality level (casual, neutral, professional)
- Verbosity reduction slider
- All prompt checkboxes (filler words, punctuation, etc.)
- Custom user instructions (if any)

**Settings applied at recording time:**
- Audio device selection
- VAD (Voice Activity Detection) enabled/disabled
- AGC (Automatic Gain Control) enabled/disabled
- Audio archival enabled/disabled

### Can I change models between recording and transcribing?

Yes! The model selection is applied when you click Transcribe, not when you start recording. You can record audio, then decide which model to use for transcription.

### What happens if I change the format preset mid-recording?

Nothing—the format preset is only applied when you click Transcribe. The recording itself is not affected by format selection.

### How does append mode work?

In append mode:
1. Record a clip and click "Stop" (not "Transcribe")
2. The audio is held in memory
3. Record another clip and click "Stop" again
4. Repeat as needed
5. Click "Transcribe" to send all clips as a single combined recording

All UI parameters (format, model, etc.) are applied to the final combined recording when you click Transcribe.

### How do the output mode buttons work?

The three output mode buttons (**App**, **Clipboard**, **Inject**) are independent toggles that can be combined in any way:

| Combination | Behavior |
|-------------|----------|
| App only | Text appears in the app window |
| Clipboard only | Text copied to clipboard (app window cleared) |
| Inject only | Text typed at cursor via ydotool |
| App + Clipboard | Text shown in app AND copied to clipboard |
| App + Inject | Text shown in app AND typed at cursor |
| Clipboard + Inject | Text copied to clipboard AND typed at cursor |
| All three | Text shown in app, copied to clipboard, AND typed at cursor |

**Status messages** only mention "invisible" actions (clipboard/inject). If text is shown in the app, that's visually obvious and doesn't need a status message.

## Related Resources

- `planning/idea-notes/` - Original concept recordings and transcripts
- `planning/apiref/` - API documentation for providers
