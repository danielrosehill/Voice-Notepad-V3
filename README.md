# Voice Notepad 

![alt text](graphics/vibe-coding-disclosure.png)

## Combined Transcription And Cleanup Desktop Utility Using Cloud Multimodal AI Models



[![Linux](https://img.shields.io/badge/Linux-FCC624?style=flat-square&logo=linux&logoColor=black)](https://github.com/danielrosehill/Voice-Notepad/releases)
[![Windows](https://img.shields.io/badge/Windows-0078D6?style=flat-square&logo=windows&logoColor=white)](https://github.com/danielrosehill/Voice-Notepad/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](LICENSE)

**Download:** [AppImage](https://github.com/danielrosehill/Voice-Notepad/releases) • [Windows Installer](https://github.com/danielrosehill/Voice-Notepad/releases) • [Debian .deb](https://github.com/danielrosehill/Voice-Notepad/releases) • [Tarball](https://github.com/danielrosehill/Voice-Notepad/releases)

---

![Voice Notepad](screenshots/1_3_0/composite-1.png)

## Why Voice Notepad?

Most voice-to-text apps use a two-step process: first transcribe with ASR, then clean up with an LLM. Voice Notepad takes a different approach—it sends your audio directly to **multimodal AI models** that can hear and transcribe in a single pass.

**Why does this matter?**

- **Context-aware cleanup**: The AI "hears" your tone, pauses, and emphasis—not just raw text
- **Verbal editing works**: Say "scratch that" or "new paragraph" and the model understands
- **Faster turnaround**: One API call instead of two
- **Lower cost**: No separate ASR charges

This is a focused tool for the growing category of audio-capable multimodal models.

## Supported Providers & Models

| Provider | Model |
|----------|-------|
| ![OpenRouter](https://img.shields.io/badge/OpenRouter-6366f1?style=flat-square) | `google/gemini-2.5-flash` |
| ![OpenRouter](https://img.shields.io/badge/OpenRouter-6366f1?style=flat-square) | `google/gemini-2.5-flash-lite` |
| ![OpenRouter](https://img.shields.io/badge/OpenRouter-6366f1?style=flat-square) | `google/gemini-2.0-flash-001` |
| ![OpenRouter](https://img.shields.io/badge/OpenRouter-6366f1?style=flat-square) | `openai/gpt-4o-audio-preview` |
| ![OpenRouter](https://img.shields.io/badge/OpenRouter-6366f1?style=flat-square) | `mistralai/voxtral-small-24b-2507` |
| ![Google](https://img.shields.io/badge/Google_(Gemini)-4285F4?style=flat-square&logo=google&logoColor=white) | `gemini-flash-latest` |
| ![Google](https://img.shields.io/badge/Google_(Gemini)-4285F4?style=flat-square&logo=google&logoColor=white) | `gemini-2.5-flash` |
| ![Google](https://img.shields.io/badge/Google_(Gemini)-4285F4?style=flat-square&logo=google&logoColor=white) | `gemini-2.5-flash-lite` |
| ![Google](https://img.shields.io/badge/Google_(Gemini)-4285F4?style=flat-square&logo=google&logoColor=white) | `gemini-2.5-pro` |
| ![OpenAI](https://img.shields.io/badge/OpenAI-412991?style=flat-square&logo=openai&logoColor=white) | `gpt-4o-audio-preview` |
| ![OpenAI](https://img.shields.io/badge/OpenAI-412991?style=flat-square&logo=openai&logoColor=white) | `gpt-4o-mini-audio-preview` |
| ![Mistral](https://img.shields.io/badge/Mistral-FF7000?style=flat-square) | `voxtral-small-latest` |
| ![Mistral](https://img.shields.io/badge/Mistral-FF7000?style=flat-square) | `voxtral-mini-latest` |

**OpenRouter** is recommended—single API key for all models with accurate per-key cost tracking.

## Features

- **One-shot transcription + cleanup**: Audio goes directly to multimodal models—no separate ASR step
- **Global hotkeys**: Record from anywhere, even when minimized (F14-F20 recommended for macro keys)
- **Voice Activity Detection**: Strips silence before upload to reduce costs
- **Automatic Gain Control**: Normalizes audio levels for consistent results
- **Cost tracking**: Monitor daily/weekly/monthly API spend (most accurate with OpenRouter)
- **Transcript history**: SQLite database stores all transcriptions with searchable metadata
- **Markdown output**: Clean, formatted text with optional source editing
- **Audio archival**: Optional Opus archival of recordings for reference

## Screenshots

![Record and History](screenshots/1_3_0/composite-1.png)
*Record tab and History tab*

![Cost and Analysis](screenshots/1_3_0/composite-2.png)
*Cost tracking and Analysis tabs*

## How Much Does Multimodal ASR Cost?

Multimodal transcription is remarkably cost-effective. Here's real usage data from Voice Notepad:

![Voice Notepad Analysis](screenshots/costs/4.png)
*114 transcriptions, 11,496 words, $0.14 total cost—about $0.001 per transcription*

![OpenRouter API Usage](screenshots/costs/2.png)
*OpenRouter API key usage showing $0.14 total spend*

![OpenRouter Activity](screenshots/costs/3.png)
*Per-request costs: $0.001–0.0015 per transcription using Gemini 2.5 Flash*

At roughly **one-tenth of a cent per transcription**, multimodal ASR through models like Gemini 2.5 Flash is cheaper than most dedicated speech-to-text services—and you get intelligent cleanup included.

## Installation

### Pre-built Packages

Download from [Releases](https://github.com/danielrosehill/Voice-Notepad/releases):

**Linux:**
- **AppImage** — Universal, run on any distro
- **.deb** — Debian/Ubuntu, install with `sudo dpkg -i`
- **Tarball** — Extract and run anywhere

**Windows:**
- **Installer (.exe)** — Recommended. Creates Start Menu shortcut, easy uninstall
- **Portable (.zip)** — Extract anywhere and run directly

> **Windows SmartScreen Note:** You may see a "Windows protected your PC" warning. This is normal for open-source software without code signing certificates. Click **"More info"** → **"Run anyway"** to proceed. Verify downloads with the SHA256 checksums in the release.

### From Source

```bash
git clone https://github.com/danielrosehill/Voice-Notepad.git
cd Voice-Notepad
./run.sh
```

The script creates a virtual environment and installs dependencies automatically.

## Configuration

Add your API key(s) via **Settings** in the app, or set environment variables:

```bash
OPENROUTER_API_KEY=your_key  # Recommended
GEMINI_API_KEY=your_key
OPENAI_API_KEY=your_key
MISTRAL_API_KEY=your_key
```

## Quick Start

1. Select your microphone and AI provider
2. Press **Record** (or `Ctrl+R`, or your global hotkey)
3. Speak naturally—say "new paragraph" or "scratch that" as needed
4. Press **Stop & Transcribe** (`Ctrl+Return`)
5. Copy or save your cleaned transcript

## Documentation

📖 **[User Manual (PDF)](docs/manuals/Voice-Notepad-User-Manual-v1.pdf)** — Full documentation including hotkey configuration, cost tracking details, and advanced settings.

## Related Resources

- [Audio-Multimodal-AI-Resources](https://github.com/danielrosehill/Audio-Multimodal-AI-Resources) — Curated list of audio-capable multimodal AI models
- [Audio-Understanding-Test-Prompts](https://github.com/danielrosehill/Audio-Understanding-Test-Prompts) — Test prompts for evaluating audio understanding

## License

MIT
