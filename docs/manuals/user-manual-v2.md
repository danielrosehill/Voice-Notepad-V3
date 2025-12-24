# AI Transcription Notepad User Manual

**Version 2.0 (Application v1.8.0)**

**Author:** Daniel Rosehill
**Repository:** [github.com/danielrosehill/Voice-Notepad](https://github.com/danielrosehill/Voice-Notepad)
**License:** MIT

---

## Table of Contents

1. [Introduction](#introduction)
2. [Installation](#installation)
3. [Getting Started](#getting-started)
4. [Main Interface](#main-interface)
   - [Record Tab](#record-tab)
   - [File Transcription Tab](#file-transcription-tab)
   - [History Tab](#history-tab)
   - [Cost Tab](#cost-tab)
   - [Prompt Stacks Tab](#prompt-stacks-tab)
5. [Settings](#settings)
   - [API Keys](#api-keys)
   - [Audio Settings](#audio-settings)
   - [Behavior Settings](#behavior-settings)
   - [Personalization](#personalization)
   - [Prompt Settings](#prompt-settings)
   - [Database](#database)
6. [Format Presets](#format-presets)
7. [Global Hotkeys](#global-hotkeys)
8. [Keyboard Shortcuts](#keyboard-shortcuts)
9. [Audio Pipeline](#audio-pipeline)
10. [Cost Tracking](#cost-tracking)
11. [Troubleshooting](#troubleshooting)

---

## Introduction

AI Transcription Notepad is a desktop application for voice recording with AI-powered transcription and cleanup. Unlike traditional speech-to-text tools that require a separate text cleanup pass, AI Transcription Notepad uses **multimodal AI models** that can process audio directly and perform both transcription and text cleanup in a single operation.

### Why Multimodal?

Most voice-to-text apps use a two-step process: first transcribe with ASR (Automatic Speech Recognition), then clean up with an LLM (Large Language Model). AI Transcription Notepad sends your audio directly to multimodal AI models that can hear and transcribe in a single pass.

This matters because:

- **The AI "hears" your tone, pauses, and emphasis** rather than just processing raw text
- **Verbal editing works naturally**: Say "scratch that" or "new paragraph" and the model understands
- **Faster turnaround**: One API call instead of two
- **Lower cost**: Single inference pass

### Key Features

- **One-shot transcription + cleanup**: Audio is sent with a cleanup prompt to multimodal models
- **Multiple AI providers**: OpenRouter (recommended), Gemini, OpenAI, and Mistral
- **File transcription**: Upload audio files (MP3, WAV, OGG, M4A, FLAC)
- **Audio compression**: Automatic downsampling to reduce file size and API costs
- **Voice Activity Detection (VAD)**: Optional silence removal before upload
- **Automatic Gain Control (AGC)**: Normalizes audio levels for consistent results
- **Cost tracking**: Monitor your API spending in real-time
- **Transcript history**: All transcriptions are saved locally with full-text search
- **Global hotkeys**: System-wide shortcuts that work even when minimized
- **Prompt Stacks**: Layer multiple AI instructions for complex workflows
- **Email personalization**: Business and personal email signatures
- **Text injection**: Automatically paste transcriptions at cursor (Wayland)
- **Append mode**: Record multiple clips and combine before transcription

---

## Installation

### Download Options

AI Transcription Notepad is available in multiple formats:

| Format | Platform | Description |
|--------|----------|-------------|
| `.exe` | Windows | Windows installer |
| `.zip` | Windows | Portable Windows version |
| `.AppImage` | Linux | Universal Linux package (runs anywhere) |
| `.deb` | Debian/Ubuntu | Native Debian package |
| `.tar.gz` | Linux | Portable archive |

Download the latest release from: https://github.com/danielrosehill/Voice-Notepad/releases

### System Requirements

- **Operating System**: Windows 10+ or Linux
- **Python**: 3.10+ (for running from source)
- **Audio**: Working microphone
- **Internet**: Required for API calls

### Linux Dependencies

```bash
sudo apt install python3 python3-venv ffmpeg portaudio19-dev
```

### Running from Source

```bash
git clone https://github.com/danielrosehill/Voice-Notepad.git
cd Voice-Notepad
./run.sh
```

The script creates a virtual environment using `uv` and installs dependencies automatically.

---

## Getting Started

### 1. Configure API Keys

Before using AI Transcription Notepad, you need to set up at least one API key:

1. Click the **Settings** button in the top-right corner
2. Go to the **API Keys** tab
3. Enter your API key for your preferred provider

**Recommended**: Use OpenRouter for access to multiple models with a single API key and accurate cost tracking.

### 2. Select Your Provider and Model

On the Record tab:

1. Choose your **Provider** from the dropdown (OpenRouter, Gemini, OpenAI, Mistral)
2. Select your preferred **Model** from the model dropdown
3. Use **Standard** or **Budget** tier buttons for quick model switching

### 3. Start Recording

1. Click **Record** or press `Ctrl+R`
2. Speak into your microphone
3. Click **Transcribe** or press `Ctrl+Return` when finished
4. Your cleaned transcription will appear in the text area

### 4. Copy or Save

- Click **Copy** to copy to clipboard
- Click **Save** to save to a file
- Enable **auto-copy** in Settings to automatically copy after transcription

---

## Main Interface

AI Transcription Notepad uses a tabbed interface with several main sections. The recording controls are always visible at the top of the window across all tabs.

### Persistent Control Bar

The control bar at the top of the window contains:

- **Status indicator**: Shows current state (Ready, Recording, Processing, etc.)
- **Duration timer**: Shows recording length
- **Segment count**: Shows number of cached segments in append mode
- **Record button**: Start a new recording
- **Pause button**: Pause/resume recording
- **Append button**: Record additional audio to combine with cached audio
- **Stop button**: Stop recording and cache audio
- **Transcribe button**: Send cached audio for transcription
- **Delete button**: Clear current recording and cached audio

### Record Tab

The Record tab is where you perform transcriptions:

**Model Selection:**
- **Provider dropdown**: Select your AI provider
- **Model dropdown**: Choose the specific model
- **Standard/Budget buttons**: Quick tier switching

**Favorites Bar:**
- Quick access to your favorite format presets
- Configure favorites in Settings → Personalization

**Prompt Controls:**
- **Format preset**: Select output format (General, Email, Todo, etc.)
- **Formality**: Casual, Neutral, or Professional tone
- **Verbosity**: Control how concise the output should be
- **Expand for more options**: Additional prompt customization

**Output Area:**
- View your transcribed text with markdown rendering
- Toggle between **Rendered** view and **Source** editing
- Word and character count displayed

**Actions:**
- **Clear**: Clear the text area
- **Save**: Save transcription to a file
- **Copy**: Copy to clipboard
- **Rewrite**: Send text back to AI for further editing

**Status Bar:**
- Shows today's spending and remaining balance (OpenRouter)

### File Transcription Tab

Transcribe existing audio files without recording:

**Supported Formats:**
- MP3, WAV, OGG, M4A, FLAC

**Features:**
- Drag and drop files or click to browse
- Multiple file selection
- Same prompt options as recording
- All transcriptions saved to history

### History Tab

The History tab provides access to all your past transcriptions:

**Features:**
- **Full-text search**: Search across all transcriptions
- **Click to preview**: Single-click shows preview
- **Double-click to load**: Load transcription into editor
- **Delete individual**: Remove specific transcriptions
- **Delete All History**: Clear entire history with confirmation

**Statistics:**
- Total transcription count
- Database size
- Audio archive size (if enabled)

### Cost Tab

The Cost tab provides detailed API usage tracking:

**Account Balance** (OpenRouter only):
- Shows your available credit balance
- Displays total credits and usage

**This API Key's Usage:**
- **Today**: Current day spending
- **This Week**: Weekly spending total
- **This Month**: Monthly spending total
- **All Time**: Lifetime spending

**Local Statistics:**
- Transcription count
- Total words and characters processed

**Export:**
- Export history to CSV (all or date range)

### Prompt Stacks Tab

Prompt Stacks allow you to layer multiple AI instructions for complex transcription scenarios:

**Use Cases:**
- Meeting notes with action items extraction
- Technical documentation with code formatting
- Multi-language transcription with translation
- Custom workflows for recurring tasks

**Features:**
- Create and save named prompt stacks
- Combine multiple prompts that stack together
- Import/export as JSON for sharing
- Toggle between legacy format system and prompt stacks

---

## Settings

Access settings by clicking the **Settings** button in the top-right corner.

### API Keys

Configure your API keys for each provider:

- **OpenRouter API Key**: Unified multi-provider access (recommended)
- **Gemini API Key**: Direct Google AI access
- **OpenAI API Key**: Direct OpenAI access
- **Mistral API Key**: Direct Mistral access

API keys are stored locally in `~/.config/voice-notepad-v3/config.json`.

### Audio Settings

Configure audio-related options:

- **Preferred microphone**: Select your primary input device with optional nickname
- **Fallback microphone**: Backup device if preferred is unavailable
- **Sample rate**: Audio quality settings (default: 48kHz)

### Behavior Settings

Customize app behavior:

- **Enable VAD**: Voice Activity Detection removes silence before upload
- **Enable AGC**: Automatic Gain Control normalizes audio levels
- **Auto-copy to clipboard**: Automatically copy transcriptions
- **Auto-paste (text injection)**: Paste transcription at cursor after copy
  - Requires `ydotool` on Wayland
- **Archive audio**: Save Opus copies of recordings (~24kbps)
- **Start minimized**: Start the app minimized to tray
- **Audio feedback**: Play beeps on recording start/stop

### Personalization

Configure user-specific settings:

- **User name**: Your name for email signatures
- **Business email**: Email address for professional communications
- **Business signature**: Full signature block for business emails
- **Personal email**: Email address for personal communications
- **Personal signature**: Signature for personal emails
- **Favorite formats**: Quick-access format presets for the main UI

### Prompt Settings

Customize the cleanup prompt:

**Always Applied (Foundation):**
- Filler word removal
- Punctuation and paragraphs
- Grammar correction
- Format detection

**Optional Enhancements:**
- Add subheadings for lengthy content
- Use markdown formatting (bold, lists)
- Remove unintentional dialogue
- Enhance AI prompts

**Writing Sample:**
Provide a sample of your writing style for the AI to mimic.

### Database

Database management options:

- **Statistics**: Total transcriptions, database size, archive size
- **FTS Status**: Shows if Full-Text Search is enabled
- **Optimize Database**: Run VACUUM to reclaim disk space
- **Refresh Statistics**: Update the displayed numbers

---

## Format Presets

AI Transcription Notepad includes many format presets organized by category:

### Foundational
- **General**: No specific formatting—general cleanup only
- **Verbatim**: Minimal transformation, closest to verbatim transcription

### Stylistic
- **Email**: Professional email format with greeting and sign-off
- **Meeting Notes**: Structured notes with action items
- **Bullet Points**: Concise bullet point list
- **Internal Memo**: Company memo format
- **Press Release**: Corporate press release structure
- **Newsletter**: Email newsletter content

### Prompts
- **AI Prompt**: General AI assistant instructions
- **Development Prompt**: Software development instructions
- **System Prompt**: AI system prompt (third-person)
- **Image Generation Prompt**: Prompts for AI image generators

### To-Do Lists
- **To-Do**: Checkbox task list format
- **Shopping List**: Categorized shopping list
- **Grocery List**: Categorized grocery list

### Blog
- **Blog Post**: Full blog post with sections
- **Blog Outline**: Blog post structure and outline
- **Blog Notes**: Unstructured blog research notes

### Documentation
- **Documentation**: Clear, structured documentation
- **Technical Docs**: Technical documentation and guides
- **README**: GitHub-style README
- **Reference Doc**: Quick-lookup reference material
- **API Documentation**: API endpoint documentation
- **SOP**: Standard Operating Procedure
- **Changelog**: Software release changelog

### Work
- **Bug Report**: Software bug report with technical details
- **Project Plan**: Project planning document

### Creative
- **Social Post**: Social media post
- **Story Notes**: Creative writing notes

### Fun & Experimental
- **Shakespearean Style**: Elizabethan English style
- **Medieval Style**: Middle English chronicle style
- **Pirate Speak**: Pirate vernacular
- **Formal Academic**: Scholarly publication style

---

## Global Hotkeys

Global hotkeys work system-wide, even when AI Transcription Notepad is minimized or unfocused.

### Current Hotkey Mapping (F15-F19)

| Key | Action | Description |
|-----|--------|-------------|
| **F15** | Simple Toggle | Start recording, or stop and transcribe immediately |
| **F16** | Tap Toggle | Start recording, or stop and cache audio (for append mode) |
| **F17** | Transcribe Only | Transcribe cached audio without starting a new recording |
| **F18** | Clear/Delete | Delete current recording and clear all cached audio |
| **F19** | Append | Start a new recording that appends to cached audio |

### Workflows

**Simple Workflow (F15 only):**
1. Press **F15** to start recording
2. Press **F15** again to stop and transcribe

**Append Workflow (F16/F17/F19):**
1. Press **F16** to start recording
2. Press **F16** again to stop and cache (audio is held in memory)
3. Press **F19** to record another segment (appends to cache)
4. Press **F17** to transcribe all cached segments together
5. Press **F18** to clear cache and start over

### Setting Up Hotkeys

Most keyboards don't have F15+ keys. Use **Input Remapper** to map other keys or buttons to these keycodes:

```bash
sudo apt install input-remapper
```

Common remapping options:
- **Pause/Break key** → F15 for toggle recording
- **USB foot pedal buttons** → F15/F17/F18 for hands-free operation
- **Extra mouse buttons** → F15 for quick dictation

See the [Hotkey Setup Guide](hotkey-setup.md) for detailed instructions.

### Technical Notes

- On Wayland: Hotkeys work via evdev (reads directly from input devices)
- Requires user to be in the 'input' group for evdev access
- Falls back to pynput/X11 on non-Linux systems
- The Settings → Hotkeys tab UI is currently disabled; configurable UI planned for future release

---

## Keyboard Shortcuts

### In-App Shortcuts

These work when the AI Transcription Notepad window is focused:

| Shortcut | Action |
|----------|--------|
| `Ctrl+R` | Start recording |
| `Ctrl+Space` | Pause/Resume recording |
| `Ctrl+Return` | Stop and transcribe |
| `Ctrl+S` | Save to file |
| `Ctrl+Shift+C` | Copy to clipboard |
| `Ctrl+N` | Clear editor |

---

## Audio Pipeline

AI Transcription Notepad processes audio through several stages before sending it to AI models:

### Processing Stages

1. **Recording**: Captures at device's native sample rate (typically 48kHz)

2. **Automatic Gain Control (AGC)**:
   - Normalizes audio levels for consistent transcription
   - Target peak: -3 dBFS
   - Maximum gain: +20 dB
   - Only boosts quiet audio—never attenuates loud audio

3. **Voice Activity Detection (VAD)**:
   - Silero VAD removes silence segments
   - Typically reduces file size by 30-50%
   - Reduces API costs

4. **Compression**:
   - Downsampled to 16kHz mono
   - Matches Gemini's internal format
   - Reduces file size ~66% vs 48kHz stereo

5. **API Submission**:
   - Audio is base64-encoded and sent with cleanup prompt
   - Response includes transcript, token counts, and cost data

6. **Storage**:
   - Transcripts saved to MongoDB-compatible database
   - Optional audio archival in Opus format (~180KB/minute)

### VAD Parameters

| Parameter | Value |
|-----------|-------|
| Sample rate | 16kHz |
| Window size | 512 samples (~32ms) |
| Threshold | 0.5 |
| Minimum speech | 250ms |
| Minimum silence | 100ms |
| Padding | 30ms |

---

## Cost Tracking

AI Transcription Notepad tracks API costs with **OpenRouter providing accurate key-specific costs** from the API.

### Cost Effectiveness

Real usage data using Gemini 2.5 Flash:
- **848 transcriptions** for **$1.17 total**
- **84,000 words** transcribed and cleaned
- About **$0.014 per 1,000 words** (1.4 cents)

### Status Bar

Shows "Today: $X.XXXX (N) | Bal: $X.XX" when using OpenRouter:
- N = number of transcriptions today
- Bal = remaining OpenRouter credit balance

### OpenRouter Tracking

OpenRouter provides the most accurate cost tracking:
- **Key-specific usage**: Uses `/api/v1/key` endpoint
- **Account balance**: Via `/api/v1/credits`
- **Activity breakdown**: Model usage via `/api/v1/activity`

### Other Providers

Non-OpenRouter providers show token-based estimates only, which may not reflect actual billing.

---

## Troubleshooting

### No Audio Detected

1. Check that your microphone is connected
2. Verify the correct microphone is selected in Settings → Audio
3. Check system audio settings (PipeWire/PulseAudio)
4. Try a different input device

### Transcription Fails

1. Verify your API key is correct in Settings
2. Check your internet connection
3. Ensure you have credits/quota with your provider
4. Try a different provider or model
5. Check if the audio file format is supported

### High API Costs

1. Enable VAD (Voice Activity Detection) to remove silence
2. Use Budget tier models when appropriate
3. Keep recordings concise
4. Monitor spending in the Cost tab

### Global Hotkeys Not Working

**On Linux/Wayland:**
1. Ensure you're in the 'input' group: `sudo usermod -aG input $USER`
2. Log out and back in after adding to group
3. Check if input-remapper is properly configured
4. Verify with `evtest` that keys are being detected

**General:**
1. Check hotkey configuration in Settings
2. Try different key combinations
3. Avoid keys that conflict with other applications

### Text Injection Not Working

1. Ensure `ydotool` is installed: `sudo apt install ydotool`
2. Start the ydotool daemon: `sudo ydotoold &`
3. Check that auto-paste is enabled in Settings → Behavior

### App Won't Start

1. Check system dependencies are installed
2. Verify Python version (3.10+)
3. Try running from terminal to see error messages:
   ```bash
   cd /path/to/Voice-Notepad
   ./run.sh
   ```
4. Reinstall the application

### Database Issues

1. Database location: `~/.config/voice-notepad-v3/mongita/`
2. Try running database optimization in Settings → Database
3. If corrupted, backup and delete the mongita folder (will lose history)

---

## Storage Locations

All data is stored in `~/.config/voice-notepad-v3/`:

| Path | Contents |
|------|----------|
| `config.json` | API keys and preferences |
| `mongita/` | MongoDB-compatible transcript database |
| `usage/` | Daily cost tracking JSON files |
| `audio-archive/` | Opus audio recordings (if enabled) |
| `models/` | Downloaded VAD model (silero_vad.onnx) |

---

## Support

- **GitHub Issues**: https://github.com/danielrosehill/Voice-Notepad/issues
- **Documentation**: https://github.com/danielrosehill/Voice-Notepad/tree/main/docs

---

*AI Transcription Notepad User Manual v2 (Application v1.8.0) - MIT License*
