# Voice Notepad 

## Combined Transcription And Cleanup Desktop Utility Using Cloud Multimodal AI Models



[![Linux](https://img.shields.io/badge/Linux-FCC624?style=flat-square&logo=linux&logoColor=black)](https://github.com/danielrosehill/Voice-Notepad/releases)
[![Windows](https://img.shields.io/badge/Windows-0078D6?style=flat-square&logo=windows&logoColor=white)](https://github.com/danielrosehill/Voice-Notepad/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](LICENSE)

**Download:** [AppImage](https://github.com/danielrosehill/Voice-Notepad/releases) • [Windows Installer](https://github.com/danielrosehill/Voice-Notepad/releases) • [Debian .deb](https://github.com/danielrosehill/Voice-Notepad/releases) • [Tarball](https://github.com/danielrosehill/Voice-Notepad/releases)


![alt text](screenshots/manual/1.png)

---

![alt text](graphics/vibe-coding-disclosure.png)

## Why Voice Notepad?

Most voice-to-text apps use a two-step process: first transcribe with ASR, then clean up with an LLM. Voice Notepad takes a different approach—it sends your audio directly to **multimodal AI models** that can hear and transcribe in a single pass.

**Why does this matter?**

- **Context-aware cleanup**: The AI "hears" your tone, pauses, and emphasis—not just raw text
- **Verbal editing works**: Say "scratch that" or "new paragraph" and the model understands
- **Faster turnaround**: One API call instead of two
- **Lower cost**: No separate ASR charges

This is a focused tool for the growing category of audio-capable multimodal models.

## Supported Providers & Models

### ![OpenRouter](https://img.shields.io/badge/OpenRouter-6366f1?style=flat-square) OpenRouter (Recommended)

Single API key for multiple models with accurate per-key cost tracking.

| Model | Description |
|-------|-------------|
| **Gemini 2.5 Flash** | Fast, cost-effective, excellent transcription quality |
| **Gemini 2.5 Flash Lite** | Ultra-low cost variant, good for quick notes |
| **Gemini 2.0 Flash** | Previous generation, still highly capable |
| **GPT-4o Audio Preview** | OpenAI's multimodal flagship, premium quality |
| **Voxtral Small** | Mistral's audio model, good multilingual support |

### ![Google](https://img.shields.io/badge/Google_(Gemini)-4285F4?style=flat-square&logo=google&logoColor=white) Google AI (Direct)

| Model | Description |
|-------|-------------|
| **Gemini Flash Latest** | Auto-updates to newest Flash model |
| **Gemini 2.5 Flash** | Current generation, best balance |
| **Gemini 2.5 Flash Lite** | Lightweight, very low cost |
| **Gemini 2.5 Pro** | Highest quality, slower and more expensive |

### ![OpenAI](https://img.shields.io/badge/OpenAI-412991?style=flat-square&logo=openai&logoColor=white) OpenAI

| Model | Description |
|-------|-------------|
| **GPT-4o Audio Preview** | Full GPT-4o with audio understanding |
| **GPT-4o Mini Audio Preview** | Faster, cheaper variant |

### ![Mistral](https://img.shields.io/badge/Mistral-FF7000?style=flat-square) Mistral AI

| Model | Description |
|-------|-------------|
| **Voxtral Small Latest** | 24B parameter audio model |
| **Voxtral Mini Latest** | Smaller, faster variant |

> **Recommendation:** Use **OpenRouter** for the best experience—one API key gives you access to all models, with accurate per-key cost tracking and live balance updates.

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
