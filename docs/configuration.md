# Configuration

Voice Notepad stores configuration in `~/.config/voice-notepad-v3/`.

## API Keys

You need an API key for at least one provider. **OpenRouter is recommended** as it provides access to multiple models through a single key.

### Setting API Keys

#### Method 1: Environment Variables

Create a `.env` file in the repository root or set system environment variables:

```bash
# Recommended - access multiple models with one key
OPENROUTER_API_KEY=your_key

# Or use provider-specific keys
GEMINI_API_KEY=your_key
OPENAI_API_KEY=your_key
MISTRAL_API_KEY=your_key
```

#### Method 2: Settings Dialog

1. Open the app
2. Click **Settings** in the toolbar
3. Enter your API keys in the **API Keys** tab

## Provider Selection

Select your preferred AI provider in the main window dropdown. Each provider offers different models:

### OpenRouter (Recommended)

OpenRouter proxies requests to multiple AI providers, giving you access to:

- `google/gemini-2.5-flash` - Fast, cost-effective
- `google/gemini-2.5-flash-lite` - Even faster/cheaper
- `openai/gpt-4o-audio-preview` - High quality
- `mistralai/voxtral-small-24b-2507` - Mistral's audio model

**Benefits:**

- Single API key for multiple providers
- Accurate cost tracking via API
- Easy model switching

### Gemini (Direct)

Direct Google AI access:

- `gemini-flash-latest` - Latest Flash model
- `gemini-2.5-flash` - Stable release
- `gemini-2.5-flash-lite` - Lite version
- `gemini-2.5-pro` - Pro tier

### OpenAI (Direct)

Direct OpenAI access:

- `gpt-4o-audio-preview` - Premium audio model
- `gpt-4o-mini-audio-preview` - Budget option
- `gpt-audio` / `gpt-audio-mini` - Shorthand aliases

### Mistral (Direct)

Direct Mistral access:

- `voxtral-small-latest` - Standard Voxtral
- `voxtral-mini-latest` - Smaller/faster

## Model Settings

Configure default models for each provider in **Settings > Models**.

## Behavior Settings

### Voice Activity Detection (VAD)

**Settings > Behavior > Enable VAD**

When enabled, silence is removed from audio before sending to the API. This:

- Reduces file size
- Lowers API costs
- Speeds up uploads

Uses [Silero VAD](https://github.com/snakers4/silero-vad) (ONNX model, ~1.4MB).

### Audio Archival

**Settings > Behavior > Archive audio recordings**

When enabled, recordings are saved in Opus format (~24kbps) to `~/.config/voice-notepad-v3/audio-archive/`.

A 1-minute recording uses approximately 180KB.

## Cleanup Prompt

The cleanup prompt instructs the AI how to process your transcription. The default prompt:

- Removes filler words (um, uh, like, etc.)
- Adds proper punctuation
- Adds paragraph spacing
- Follows verbal instructions in the recording
- Adds subheadings for lengthy content
- Returns markdown output

Customize the prompt in **Settings > Prompt**.

## Configuration Files

All configuration is stored in `~/.config/voice-notepad-v3/`:

| File/Directory | Purpose |
|----------------|---------|
| `config.json` | API keys, model selections, preferences |
| `transcriptions.db` | SQLite database of transcript history |
| `usage/` | Daily cost tracking JSON files |
| `audio-archive/` | Opus audio archives (if enabled) |
| `models/` | Downloaded VAD model |
