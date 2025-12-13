# Voice Notepad

![Voice Notepad Screenshot](../screenshots/v1/image.png)

Voice Notepad is a desktop application that offers multimodal audio models for single-operation transcription and light text cleanup. Unlike traditional ASR + LLM pipelines, this app sends audio directly to AI models that handle both transcription and cleanup in a single pass.

## Key Features

- **One-shot transcription + cleanup** - Audio is sent with a cleanup prompt to multimodal models
- **Multiple AI providers** - OpenRouter (recommended), Gemini, OpenAI, and Mistral
- **Cost tracking** - Monitor API spend with accurate usage data
- **Transcript history** - SQLite database stores all transcriptions
- **Voice Activity Detection** - Optional silence removal before API upload
- **Global hotkeys** - System-wide shortcuts for hands-free operation

## Why Multimodal?

Traditional speech-to-text workflows require two steps:

1. ASR (Automatic Speech Recognition) to convert audio to text
2. LLM pass to clean up the raw transcription

Voice Notepad uses **audio multimodal models** that can directly process audio input. This single-pass approach:

- Reduces latency (one API call instead of two)
- Produces more contextually aware cleanup (the model "hears" the original audio)
- Supports verbal instructions embedded in the recording (e.g., "delete that last part")

## Supported Providers

| Provider | Description |
|----------|-------------|
| **OpenRouter** (Recommended) | Access multiple models (Gemini, GPT-4o, Voxtral) through a single API key with accurate cost tracking |
| Gemini | Direct Google AI access |
| OpenAI | GPT-4o audio models |
| Mistral | Voxtral speech models |

## Quick Start

```bash
# Clone the repository
git clone https://github.com/danielrosehill/Voice-Notepad.git
cd Voice-Notepad

# Run the app
./run.sh
```

See the [Installation](installation.md) guide for detailed setup instructions.

## Related Projects

- [Audio-Multimodal-AI-Resources](https://github.com/danielrosehill/Audio-Multimodal-AI-Resources) - Curated list of audio-capable multimodal AI models and APIs
- [Audio-Understanding-Test-Prompts](https://github.com/danielrosehill/Audio-Understanding-Test-Prompts) - Test prompts for evaluating audio understanding capabilities
